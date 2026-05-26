#!/usr/bin/env python3
"""Render the paper-vs-measured replication scatter as a first-class figure.

Promotes deck slide S1 (currently hand-coded inline SVG in
``paper/deck/index.html``) to a reproducible figure that reads the v1
sweep parquet + the per-policy ``paper_reported_success`` rates from
``configs/policies.yaml`` and emits an SVG (transparent bg, paper) plus
a PNG (white bg, dpi=200, deck/README).

For each (policy, env) cell with both a paper rate and a measured rate
we plot a single point::

    x = paper-reported success rate
    y = measured success rate (Wilson 95% CI vertical error bar)
    color = traffic light vs paper
        green  (#34d399)  measured >= paper
        yellow (#fbbf24)  paper within the measured 95% CI
        red    (#f87171)  measured + CI upper bound still below paper

XVLA rows are excluded by default (deferred to v1.1 per
``docs/DEFERRED_POLICIES.md``); pass ``--show-deferred`` to include them
greyed out (``#7d8593``).

Outputs::

    docs/assets/fig-replication-scatter.svg
    docs/assets/fig-replication-scatter.png

Usage::

    python scripts/replication_scatter.py
    python scripts/replication_scatter.py --show-deferred
    python scripts/replication_scatter.py \\
        --results results/sweep-full/results.parquet \\
        --policies configs/policies.yaml \\
        --out-dir docs/assets
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import yaml

from lerobot_bench.stats import wilson_ci

# Deck palette (paper/deck/index.html). Solid marker + bar colors must
# match the supplementary slide S1 so the figure and the deck agree.
COLOR_GREEN = "#34d399"
COLOR_YELLOW = "#fbbf24"
COLOR_RED = "#f87171"
COLOR_MUTE = "#7d8593"

# Policies whose cells are deferred to v1.1; greyed out under --show-deferred.
DEFERRED_POLICIES = frozenset({"xvla_libero"})


@dataclass(frozen=True)
class Point:
    policy: str
    env: str
    paper: float
    measured: float
    lo: float
    hi: float
    n: int
    successes: int
    deferred: bool

    @property
    def label(self) -> str:
        # Short policy names for the legend / point label.
        short = self.policy.replace("_libero", "").replace("diffusion_policy", "diffusion")
        return f"{short} · {self.env}"

    @property
    def color(self) -> str:
        if self.deferred:
            return COLOR_MUTE
        if self.measured >= self.paper:
            return COLOR_GREEN
        if self.lo <= self.paper <= self.hi:
            return COLOR_YELLOW
        if self.hi < self.paper:
            return COLOR_RED
        # measured < paper but paper still in [lo, hi] handled above;
        # fall-through for paper > hi is the red case. Defensive default:
        return COLOR_RED


def load_paper_rates(policies_yaml: Path) -> dict[tuple[str, str], float]:
    """Read ``paper_reported_success`` per (policy, env) from configs/policies.yaml.

    Baselines and policies without a published reference are omitted.
    """
    with policies_yaml.open() as f:
        cfg = yaml.safe_load(f)
    rates: dict[tuple[str, str], float] = {}
    for entry in cfg.get("policies", []):
        prs = entry.get("paper_reported_success") or {}
        for env_name, rate in prs.items():
            rates[(entry["name"], env_name)] = float(rate)
    return rates


def collect_points(
    results: Path,
    policies_yaml: Path,
    *,
    include_deferred: bool,
) -> list[Point]:
    df = pd.read_parquet(results)
    rates = load_paper_rates(policies_yaml)

    cells = (
        df.groupby(["policy", "env"])
        .agg(n=("success", "size"), succ=("success", "sum"))
        .reset_index()
    )

    points: list[Point] = []
    for _, row in cells.iterrows():
        key = (row["policy"], row["env"])
        if key not in rates:
            continue
        is_deferred = row["policy"] in DEFERRED_POLICIES
        if is_deferred and not include_deferred:
            continue
        n = int(row["n"])
        successes = int(row["succ"])
        lo, hi = wilson_ci(successes, n)
        points.append(
            Point(
                policy=row["policy"],
                env=row["env"],
                paper=rates[key],
                measured=successes / n,
                lo=lo,
                hi=hi,
                n=n,
                successes=successes,
                deferred=is_deferred,
            )
        )
    # Stable, readable ordering: deferred last; otherwise by (policy, env).
    points.sort(key=lambda p: (p.deferred, p.policy, p.env))
    return points


# Manual label offsets keep the labels from sitting on top of each other
# when several SmolVLA points cluster in the top-right corner. (dx, dy)
# in axis units; we draw a thin leader when the label is off the marker.
LABEL_OFFSETS: dict[tuple[str, str], tuple[float, float]] = {
    ("smolvla_libero", "libero_spatial"): (-0.02, -0.07),
    ("smolvla_libero", "libero_object"): (-0.02, -0.10),
    ("smolvla_libero", "libero_goal"): (0.02, 0.03),
    ("smolvla_libero", "libero_10"): (0.04, -0.02),
    ("diffusion_policy", "pusht"): (-0.04, 0.06),
    ("act", "aloha_transfer_cube"): (0.04, 0.02),
    ("xvla_libero", "libero_spatial"): (-0.02, 0.04),
    ("xvla_libero", "libero_object"): (-0.02, 0.08),
    ("xvla_libero", "libero_goal"): (-0.02, 0.12),
    ("xvla_libero", "libero_10"): (-0.02, 0.16),
}


def _draw(points: list[Point], *, transparent: bool) -> plt.Figure:
    fig, ax = plt.subplots(figsize=(8.0, 6.0))

    # Diagonal first so markers sit on top.
    ax.plot(
        [0, 1],
        [0, 1],
        color=COLOR_GREEN,
        linestyle="--",
        linewidth=1.4,
        alpha=0.75,
        label="y = x · perfect replication",
        zorder=1,
    )

    edge = "white" if not transparent else "none"
    for p in points:
        # Clamp tiny FP negatives at the [0,1] boundary so matplotlib's
        # errorbar yerr-positivity check doesn't trip on Wilson(0, n).
        yerr_lo = max(0.0, p.measured - p.lo)
        yerr_hi = max(0.0, p.hi - p.measured)
        ax.errorbar(
            p.paper,
            p.measured,
            yerr=[[yerr_lo], [yerr_hi]],
            fmt="o",
            color=p.color,
            ecolor=p.color,
            elinewidth=1.4,
            capsize=4,
            markersize=8,
            markeredgecolor=edge,
            markeredgewidth=1.2,
            zorder=3,
        )
        dx, dy = LABEL_OFFSETS.get((p.policy, p.env), (0.02, 0.02))
        ax.annotate(
            p.label,
            xy=(p.paper, p.measured),
            xytext=(p.paper + dx, p.measured + dy),
            fontsize=9,
            fontfamily="monospace",
            color=p.color,
            ha="left" if dx >= 0 else "right",
            va="center",
            zorder=4,
        )

    ax.set_xlim(-0.02, 1.04)
    ax.set_ylim(-0.02, 1.04)
    ax.set_xlabel("paper-reported success rate", fontsize=11)
    ax.set_ylabel("measured success rate (Wilson 95% CI)", fontsize=11)
    ax.set_xticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.grid(True, linestyle=":", linewidth=0.6, alpha=0.5)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="lower right", fontsize=9, frameon=False)

    # Tighten without losing the labels that overflow rightward.
    fig.tight_layout()
    return fig


def render(points: list[Point], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    svg_path = out_dir / "fig-replication-scatter.svg"
    png_path = out_dir / "fig-replication-scatter.png"

    # SVG: transparent background for paper inclusion.
    fig_svg = _draw(points, transparent=True)
    fig_svg.savefig(svg_path, format="svg", transparent=True, bbox_inches="tight")
    plt.close(fig_svg)

    # PNG: white background dpi=200 for deck + README.
    fig_png = _draw(points, transparent=False)
    fig_png.savefig(png_path, format="png", dpi=200, facecolor="white", bbox_inches="tight")
    plt.close(fig_png)

    return svg_path, png_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--results",
        type=Path,
        default=Path("results/sweep-full/results.parquet"),
        help="Path to the sweep results parquet (default: results/sweep-full/results.parquet).",
    )
    parser.add_argument(
        "--policies",
        type=Path,
        default=Path("configs/policies.yaml"),
        help="Path to the policy registry YAML (default: configs/policies.yaml).",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("docs/assets"),
        help="Output directory (default: docs/assets).",
    )
    parser.add_argument(
        "--show-deferred",
        action="store_true",
        help="Include deferred policies (XVLA) greyed out.",
    )
    args = parser.parse_args(argv)

    if not args.results.exists():
        print(f"error: results parquet not found at {args.results}", file=sys.stderr)
        return 2
    if not args.policies.exists():
        print(f"error: policies yaml not found at {args.policies}", file=sys.stderr)
        return 2

    points = collect_points(args.results, args.policies, include_deferred=args.show_deferred)
    if not points:
        print("error: no (policy, env) cells had both paper and measured rates", file=sys.stderr)
        return 2

    svg_path, png_path = render(points, args.out_dir)

    print(f"plotted {len(points)} cell(s):")
    for p in points:
        flag = " [deferred]" if p.deferred else ""
        print(
            f"  {p.policy:>18s} · {p.env:<22s} paper={p.paper:.3f} measured={p.measured:.3f} "
            f"CI=[{p.lo:.3f},{p.hi:.3f}] n={p.n} color={p.color}{flag}"
        )
    print(f"wrote {svg_path}")
    print(f"wrote {png_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
