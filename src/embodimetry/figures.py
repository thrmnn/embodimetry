"""Parameterized figure-generation pipeline for embodimetry.

Four canonical figures (forest plot, ACT normalization 2x2 ablation,
paper-vs-measured replication scatter, v1.1 failure-taxonomy matrix)
render at three target styles (`paper`, `deck`, `web`). Each figure
function takes a ``style`` kwarg and writes the rendered file(s) to
``out_dir / style / name.<ext>`` per the style's ``formats`` tuple.
Style dicts are the only public surface for visual configuration —
figure functions must NOT take colors as kwargs.

Data sources (cited inline in each function's docstring):

- Forest plot: ``results/sweep-full/results.parquet`` (PR #74 sweep).
- Replication scatter: parquet + ``configs/policies.yaml``
  ``paper_reported_success`` blocks (Zhao 2023, Shukor 2025, etc. —
  see policies.yaml comments for per-cell citations); SmolVLA suite
  points come from the v1.1 parquet
  (``results/sweep-v11-libero/results.parquet``) when supplied.
- Failure taxonomy: ``docs/assets/failure-taxonomy-labels-v11.csv``
  (SWEEP_V11_LIBERO_RESULTS.md § 10 labeling pass).

Every render call writes to ``paper/figures/{style}/{name}.{ext}``.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Literal

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.figure import Figure
from matplotlib.transforms import Bbox

from embodimetry.policies import PolicyRegistry
from embodimetry.stats import (
    LIBERO_SUITES,
    cluster_mean_t_ci,
    pool_binomial,
    wilson_ci,
    wilson_halfwidth_at_p,
)

Style = Literal["paper", "deck", "web"]

# Sort order for the leaderboard cells. xvla_libero is intentionally
# absent — deferred from the v1 leaderboard per PR #82 / xvla v1.1
# deferral memo, and exclude_xvla() drops it from inputs.
_POLICY_ORDER: tuple[str, ...] = (
    "act",
    "diffusion_policy",
    "smolvla_libero",
    "no_op",
    "random",
)
# pusht + aloha first, then each LIBERO suite in base (t0) → _t1.._t9
# task order so forest_plot() sorts deterministically by suite then task
# index for v1.1's 40 LIBERO envs (was 6 envs in v1.0; the 36 _tN envs
# previously fell to rank 99 and sorted non-deterministically).
_LIBERO_SUITES: tuple[str, ...] = (
    "libero_spatial",
    "libero_object",
    "libero_goal",
    "libero_10",
)
_ENV_ORDER: tuple[str, ...] = (
    "pusht",
    "aloha_transfer_cube",
    *(suite if t == 0 else f"{suite}_t{t}" for suite in _LIBERO_SUITES for t in range(10)),
)

# Minimum-detectable-effect band half-width at p=0.5, N=250 (DESIGN.md
# § Methodology: 2 * wilson_halfwidth_at_p(0.5, 250) ≈ 0.123). Used by
# replication_scatter() to greyscale "indistinguishable from paper"
# cells. Computed at module load so tests can read it.
MDE_BAND: float = 2.0 * wilson_halfwidth_at_p(0.5, 250)


PAPER_STYLE: dict[str, Any] = {
    "figsize": (3.5, 2.5),
    "font_family": "serif",
    "font_size": 8,
    "line_width": 0.8,
    "palette": {"ok": "#2c7fb8", "warm": "#d95f02", "fail": "#c91414", "muted": "#888888"},
    "bg": "white",
    "fg": "#1a1a1a",
    "dpi": 300,
    "formats": ("svg", "pdf"),
}
DECK_STYLE: dict[str, Any] = {
    "figsize": (8.0, 4.5),
    "font_family": "Instrument Sans, sans-serif",
    "font_size": 18,
    "line_width": 2.0,
    "palette": {"ok": "#34d399", "warm": "#fbbf24", "fail": "#f87171", "muted": "#a78bfa"},
    "bg": "#0a0d12",
    "fg": "#f5f7fa",
    "dpi": 120,
    "formats": ("png",),
}
WEB_STYLE: dict[str, Any] = {
    "figsize": (6.0, 4.0),
    "font_family": "Instrument Sans, system-ui, sans-serif",
    "font_size": 12,
    "line_width": 1.2,
    "palette": {"ok": "#34d399", "warm": "#fbbf24", "fail": "#f87171", "muted": "#a78bfa"},
    "bg": "transparent",
    "fg": "#1a1a1a",
    "dpi": 96,
    "formats": ("svg",),
}

STYLES: dict[Style, dict[str, Any]] = {
    "paper": PAPER_STYLE,
    "deck": DECK_STYLE,
    "web": WEB_STYLE,
}

# Per-policy color (used by forest plot + replication scatter). Pulled
# from a small qualitative ramp so colours hold up at print-grayscale —
# the paper style overrides this with a darker, B&W-safe ramp.
_POLICY_COLORS_PAPER: dict[str, str] = {
    "act": "#1b9e77",
    "diffusion_policy": "#7570b3",
    "smolvla_libero": "#d95f02",
    "no_op": "#666666",
    "random": "#999999",
}
_POLICY_COLORS_DARK: dict[str, str] = {
    "act": "#34d399",
    "diffusion_policy": "#7aa3ff",
    "smolvla_libero": "#fbbf24",
    "no_op": "#7d8593",
    "random": "#a78bfa",
}


def apply_style(style: Style) -> dict[str, Any]:
    """Return a deep copy of the named style dict and apply rcParams.

    Returning a copy (not a reference) so callers can mutate the returned
    dict (e.g. to override a single color in a one-off render) without
    poisoning the module-level STYLES singleton — tests pin this.

    The matplotlib rcParams are mutated in place; the caller is expected
    to wrap repeated renders inside a single ``apply_style`` to amortise
    the cost. Reverting rcParams is the caller's responsibility (e.g.
    ``with plt.rc_context(...)``) — these figures all save + close
    inside a single function call so cross-figure rcParam leakage is not
    observed in practice.
    """
    if style not in STYLES:
        raise ValueError(f"unknown style {style!r}; expected one of {sorted(STYLES)}")
    s = copy.deepcopy(STYLES[style])
    plt.rcParams["font.family"] = s["font_family"]
    plt.rcParams["font.size"] = s["font_size"]
    plt.rcParams["axes.linewidth"] = s["line_width"]
    plt.rcParams["axes.edgecolor"] = s["fg"]
    plt.rcParams["axes.labelcolor"] = s["fg"]
    plt.rcParams["xtick.color"] = s["fg"]
    plt.rcParams["ytick.color"] = s["fg"]
    plt.rcParams["text.color"] = s["fg"]
    plt.rcParams["axes.titlesize"] = s["font_size"] + 1
    plt.rcParams["savefig.dpi"] = s["dpi"]
    return s


def _policy_color_map(style: Style) -> dict[str, str]:
    return _POLICY_COLORS_PAPER if style == "paper" else _POLICY_COLORS_DARK


def _apply_bg(fig: Figure, style_dict: dict[str, Any]) -> None:
    bg = style_dict["bg"]
    if bg == "transparent":
        fig.patch.set_alpha(0.0)
        for ax in fig.axes:
            ax.set_facecolor("none")
    else:
        fig.patch.set_facecolor(bg)
        for ax in fig.axes:
            ax.set_facecolor(bg)


def _save_all(fig: Figure, name: str, style: Style, out_dir: Path) -> list[Path]:
    """Save ``fig`` in every format of ``style`` under ``out_dir / style /``.

    Returns the list of written paths in the order they appear in
    ``STYLES[style]['formats']``. Each path is logged + sized so the
    CLI can render the operator-facing summary table.
    """
    style_dict = STYLES[style]
    target_dir = out_dir / style
    target_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    transparent = style_dict["bg"] == "transparent"
    for ext in style_dict["formats"]:
        path = target_dir / f"{name}.{ext}"
        fig.savefig(
            path,
            dpi=style_dict["dpi"],
            bbox_inches="tight",
            transparent=transparent,
            facecolor=(style_dict["bg"] if not transparent else "none"),
        )
        paths.append(path)
    plt.close(fig)
    return paths


def _filter_leaderboard(df: pd.DataFrame) -> pd.DataFrame:
    """Drop xvla rows (deferred from leaderboard per PR #82)."""
    return df.loc[~df["policy"].str.startswith("xvla"), :].copy()


# --------------------------------------------------------------------- #
# Figure 1 — forest plot                                                #
# --------------------------------------------------------------------- #


def forest_plot(df: pd.DataFrame, *, style: Style, out_dir: Path) -> list[Path]:
    """Per-cell success rate + Wilson 95% CI forest plot.

    Source: ``results/sweep-full/results.parquet`` (PR #74). Each cell
    is one ``(policy, env)`` pair; pooled rate across the cell's
    ``5 × n_episodes_per_seed`` episodes, with Wilson 95% CI per
    ``embodimetry.stats.wilson_ci`` (Wilson 1927; Agresti & Coull 1998).

    xvla_libero rows are excluded (deferred from the v1 leaderboard per
    PR #82). The vertical dotted line is the random-baseline pooled rate
    across all envs, for "is this policy beating random?" reference.
    """
    df = _filter_leaderboard(df)
    rows: list[dict[str, Any]] = []
    for (policy, env), grp in df.groupby(["policy", "env"], sort=False):
        n = len(grp)
        k = int(grp["success"].sum())
        rate = k / n if n else 0.0
        lo, hi = wilson_ci(k, n) if n else (0.0, 0.0)
        rows.append({"policy": policy, "env": env, "rate": rate, "lo": lo, "hi": hi, "n": n})

    cells = pd.DataFrame(rows)
    p_rank = {p: i for i, p in enumerate(_POLICY_ORDER)}
    e_rank = {e: i for i, e in enumerate(_ENV_ORDER)}
    cells["_p"] = cells["policy"].map(lambda p: p_rank.get(str(p), 99))
    cells["_e"] = cells["env"].map(lambda e: e_rank.get(str(e), 99))
    cells = cells.sort_values(["_p", "_e"], ascending=[True, True]).reset_index(drop=True)

    s = apply_style(style)
    # The forest plot's row count drives height: a fixed figsize cramps
    # the per-cell labels into the style's default height. Scale height to
    # keep ~0.22 in/row at all styles so v1.1's 23+ rows aren't cramped,
    # capped at 8x the style's default height so a pathological row count
    # can't produce an unbounded canvas.
    base_w, base_h = s["figsize"]
    per_row = 0.22 if style == "paper" else 0.35
    height = max(base_h, min(8.0 * base_h, per_row * len(cells) + 1.0))
    fig, ax = plt.subplots(figsize=(base_w, height))

    color_map = _policy_color_map(style)
    y = np.arange(len(cells))
    # A bare LIBERO suite name is that suite's task-0 env under the sweep's
    # naming convention ({suite} = task 0, {suite}_tN = task N) — mark it so
    # single-task cells can't be misread as suite-level rates (DEF-021).
    labels = [
        f"{r['policy']} x {r['env']} (task 0)"
        if str(r["env"]) in LIBERO_SUITES
        else f"{r['policy']} x {r['env']}"
        for _, r in cells.iterrows()
    ]
    colors = [color_map.get(str(r["policy"]), s["palette"]["muted"]) for _, r in cells.iterrows()]
    rates = cells["rate"].to_numpy(dtype=float)
    # Clip to handle float noise from Wilson at k=0 / k=n (lo/hi can
    # drift ~1e-19 past the rate, which trips matplotlib's xerr>=0 check).
    err_lo = np.clip(rates - cells["lo"].to_numpy(dtype=float), 0.0, None)
    err_hi = np.clip(cells["hi"].to_numpy(dtype=float) - rates, 0.0, None)

    for i, color in enumerate(colors):
        ax.errorbar(
            rates[i],
            y[i],
            xerr=[[err_lo[i]], [err_hi[i]]],
            fmt="none",
            ecolor=color,
            elinewidth=s["line_width"],
            capsize=2.5,
            alpha=0.9,
        )
    ax.scatter(rates, y, c=colors, s=22, zorder=3, edgecolors=s["fg"], linewidths=0.4)

    random_rate = cells.loc[cells["policy"] == "random", "rate"].mean()
    if pd.notna(random_rate):
        ax.axvline(
            float(random_rate),
            color=s["palette"]["muted"],
            linestyle=":",
            linewidth=s["line_width"],
            alpha=0.7,
        )

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=max(6, s["font_size"] - 2))
    ax.invert_yaxis()
    ax.set_xlim(-0.02, 1.02)
    ax.set_xlabel("success rate")
    ax.set_title("Per-cell success rates - 95% Wilson CI")
    ax.grid(True, axis="x", linestyle="--", alpha=0.25)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    _apply_bg(fig, s)
    fig.tight_layout()
    return _save_all(fig, "forest_plot", style, out_dir)


# --------------------------------------------------------------------- #
# Figure 4 — ACT normalization 2x2 ablation heatmap                     #
# --------------------------------------------------------------------- #

# Canonical published cells for the ACT x aloha_transfer_cube controlled
# 2x2 ablation (paper Table tab:act-ablation, paper/main.tex L354-377).
# Rows = normalization {Buggy (v1.0.0), Fixed (PR #51)}; columns =
# inference {Hub-default (coeff=None, n_steps=100), Paper (coeff=0.01,
# n_steps=1)}. Each cell is N=250 (5 seeds x 50 episodes). Wilson 95%
# CIs are the doc-published values. HARDCODED — these are stable canonical
# numbers and are NOT read from parquet (see PROBE_RESULTS / paper).
_ACT_NORM_ABLATION: dict[tuple[int, int], dict[str, Any]] = {
    # (row, col): row 0 = buggy, row 1 = fixed; col 0 = hub, col 1 = paper.
    (0, 0): {"rate": 0.016, "ci": (0.006, 0.040)},  # buggy + hub
    (0, 1): {"rate": 0.016, "ci": (0.006, 0.040)},  # buggy + paper
    (1, 0): {"rate": 0.812, "ci": (0.759, 0.856)},  # fixed + hub
    (1, 1): {"rate": 0.768, "ci": (0.712, 0.816)},  # fixed + paper
}
_ACT_NORM_ROW_LABELS: tuple[str, str] = ("Buggy\n(v1.0.0)", "Fixed\n(PR #51)")
_ACT_NORM_COL_LABELS: tuple[str, str] = (
    "Hub-default\ncoeff=None, n_steps=100",
    "Paper\ncoeff=0.01, n_steps=1",
)


def act_norm_ablation_2x2(*, style: Style, out_dir: Path) -> list[Path]:
    """ACT x aloha_transfer_cube controlled 2x2 normalization ablation.

    A 2x2 heatmap crossing normalization {Buggy (v1.0.0), Fixed (PR #51)}
    against inference settings {Hub-default (coeff=None, n_steps=100),
    Paper (coeff=0.01, n_steps=1)}. Cells are colored by success rate on
    the viridis ramp (CVD-safe, print-grayscale-safe) and annotated with
    the pooled rate and its Wilson 95% CI. The figure makes the headline
    finding visual: normalization is the load-bearing variable (rows
    differ by ~0.8), while the inference-settings effect within the fixed
    row is small and inconclusive at this N (paired McNemar p=0.23, see
    the paper's Table tab:act-ablation).

    Source: canonical published cells (paper
    Table~\\ref{tab:act-ablation}, ``scripts/probes/probe_act_normalization_ablation.py``),
    HARDCODED here as ``_ACT_NORM_ABLATION``. N=250/cell (5 seeds x 50 ep).
    """
    s = apply_style(style)
    # Square-ish heatmap: widen the paper default slightly so the two
    # column headers (each two lines) don't collide.
    base_w, base_h = s["figsize"]
    fig, ax = plt.subplots(figsize=(base_w, base_h))

    grid = np.array(
        [[_ACT_NORM_ABLATION[(r, c)]["rate"] for c in (0, 1)] for r in (0, 1)],
        dtype=float,
    )
    # viridis (sequential, CVD-safe — RdYlGn is not). vmin/vmax pinned to
    # [0, 1] so the color encodes absolute success rate, not the data's
    # own range.
    im = ax.imshow(grid, cmap="viridis", vmin=0.0, vmax=1.0, aspect="auto")

    ann_fs = max(6, s["font_size"] - 1)
    ci_fs = max(5, s["font_size"] - 3)
    for r in (0, 1):
        for c in (0, 1):
            cell = _ACT_NORM_ABLATION[(r, c)]
            rate = cell["rate"]
            lo, hi = cell["ci"]
            # viridis is dark (purple/blue) below ~0.6 and light
            # (green/yellow) above: flip annotation ink at that luminance
            # crossover so text stays legible across the whole ramp.
            txt_color = "#111111" if rate > 0.60 else "#ffffff"
            ax.text(
                c,
                r - 0.10,
                f"{rate * 100:.1f}%",
                ha="center",
                va="center",
                fontsize=ann_fs,
                fontweight="bold",
                color=txt_color,
            )
            ax.text(
                c,
                r + 0.14,
                f"[{lo * 100:.1f}, {hi * 100:.1f}]",
                ha="center",
                va="center",
                fontsize=ci_fs,
                color=txt_color,
            )

    ax.set_xticks([0, 1])
    ax.set_xticklabels(_ACT_NORM_COL_LABELS, fontsize=max(6, s["font_size"] - 2))
    ax.set_yticks([0, 1])
    ax.set_yticklabels(_ACT_NORM_ROW_LABELS, fontsize=max(6, s["font_size"] - 2))
    ax.set_xlabel("inference settings", fontsize=max(6, s["font_size"] - 1))
    ax.set_ylabel("normalization", fontsize=max(6, s["font_size"] - 1))
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-0.5, 2, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 2, 1), minor=True)
    ax.grid(which="minor", color=s["bg"] if s["bg"] != "transparent" else "white", linewidth=2)
    ax.tick_params(which="minor", length=0)

    ax.set_title(
        "ACT x aloha: normalization is load-bearing;\ninference effect inconclusive at this N",
        fontsize=s["font_size"],
        pad=6,
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("success rate", fontsize=max(6, s["font_size"] - 2))
    cbar.ax.tick_params(labelsize=max(5, s["font_size"] - 3), length=0)

    _apply_bg(fig, s)
    # Reserve headroom for the title and a left strip for the row labels +
    # y-label so bbox_inches="tight" in _save_all doesn't crop them.
    fig.tight_layout(rect=(0.02, 0.0, 1.0, 0.96))
    return _save_all(fig, "act_norm_ablation", style, out_dir)


# --------------------------------------------------------------------- #
# Figure 3 — paper-vs-measured replication scatter                      #
# --------------------------------------------------------------------- #

# ACT × aloha_transfer_cube pre-fix (normalization bug) point. The
# canonical parquet (results/sweep-full/results.parquet) carries the
# corrected, norm-FIXED cell (206/250 = 0.824 [0.772, 0.866]; the #177
# splice landed). replication_scatter() still prefers the rerun parquet
# (results/sweep-full/results-act-rerun.parquet) as the cell's source of
# record — the two agree by construction post-splice — and keeps this
# 0.016 reading only as a small, explicitly-labeled "pre-fix" annotation
# showing the jump our normalization fix produced — NOT as the headline
# cell.
_ACT_PREFIX_BUG_POINT: dict[str, Any] = {
    "policy": "act",
    "env": "aloha_transfer_cube",
    "paper": 0.50,
    "measured": 0.016,
    "lo": 0.006,
    "hi": 0.040,
    "n": 250,
    # Render in the muted/grey ink so it reads as a deprecated annotation,
    # not a live measured cell competing with the 0.824 main point.
    "inside_mde": True,
}

# Canonical norm-fixed ACT × aloha_transfer_cube value (post-#51), pooled
# 0.824 [0.772, 0.866] at N=250. Lives in the rerun parquet; mirrors the
# value the publish preflight + tests/test_headline_value_consistency.py
# guard as the headline scalar.
_ACT_ALOHA_RERUN_PATH = Path("results/sweep-full/results-act-rerun.parquet")
_ACT_ALOHA_FIXED_RATE = 0.824
_ACT_ALOHA_FIXED_CI: tuple[float, float] = (0.772, 0.866)


def _act_aloha_rerun_cell(rerun_path: Path = _ACT_ALOHA_RERUN_PATH) -> dict[str, Any] | None:
    """Return the corrected act×aloha cell (k, n, pooled, Wilson CI) or ``None``.

    Sources the norm-FIXED act×aloha_transfer_cube cell from the committed
    rerun parquet (``results/sweep-full/results-act-rerun.parquet``) WITHOUT
    requiring the owner-gated splice into the canonical parquet (#177). The
    row mask mirrors ``scripts/merge_corrected_act_rows.py._act_aloha_mask``
    (policy == "act" AND env contains "aloha") so the figure agrees with the
    merge tool by construction. The #177 splice has landed, so the canonical
    parquet carries the same corrected cell; returning ``None`` when the
    gitignored rerun parquet is absent (fresh CI checkout) therefore falls
    back to an identical value from the passed-in ``df``.
    """
    if not rerun_path.exists():
        return None
    try:
        rerun = pd.read_parquet(rerun_path)
    except (OSError, ValueError):
        return None
    if "errored" in rerun.columns:
        rerun = rerun[~rerun["errored"].fillna(False)]
    mask = (rerun["policy"] == "act") & rerun["env"].astype(str).str.contains("aloha")
    sub = rerun[mask]
    n = len(sub)
    if n == 0:
        return None
    k = int(sub["success"].astype(float).sum())
    lo, hi = wilson_ci(k, n)
    return {"k": k, "n": n, "measured": k / n, "lo": lo, "hi": hi}


def _collect_replication_rows(
    df: pd.DataFrame,
    registry: PolicyRegistry,
    *,
    rerun_path: Path = _ACT_ALOHA_RERUN_PATH,
    v11_df: pd.DataFrame | None = None,
) -> list[dict[str, Any]]:
    """Collect (paper, measured) cells, sourcing the corrected ACT cell.

    For the act×aloha_transfer_cube cell specifically the MAIN point is the
    norm-FIXED 0.824 [0.772, 0.866] reading pulled from the rerun parquet
    (see ``_act_aloha_rerun_cell``); the canonical parquet carries the same
    corrected cell post-splice (#177), so the ``df`` fallback agrees. Every
    other cell pools straight from ``df``.

    smolvla_libero × LIBERO suite cells are special-cased: the paper numbers
    in ``policies.yaml`` are 10-task suite averages, but the sweeps emit
    per-task env keys (``{suite}`` = task 0, ``{suite}_t1``..``_t9`` =
    tasks 1-9), so the bare-suite mask of the generic path would match ONLY
    task 0 — not apples-to-apples against a 10-task average. When ``v11_df``
    (the v1.1 all-10-task sweep parquet) is supplied, each suite row is the
    equal-task suite average with a **cluster-robust 95% t-CI over the 10
    per-task rates** (:func:`embodimetry.stats.cluster_mean_t_ci` — task as
    the sampling unit; an episode-iid Wilson CI is vetoed at design effect
    25–65×, SWEEP_V11 § 6.2) plus the per-task rates themselves for the
    figure's per-task dots. Without ``v11_df`` the row falls back to pooling
    whatever member cells exist in ``df`` via
    :func:`embodimetry.stats.pool_binomial`, recording ``n_tasks_present`` /
    ``n_tasks_expected`` so partial coverage is annotated, never silently
    overstated.
    """
    rerun_cell = _act_aloha_rerun_cell(rerun_path)
    rows: list[dict[str, Any]] = []
    for spec in registry:
        if spec.paper_reported_success is None:
            continue
        for env, paper_rate in spec.paper_reported_success.items():
            if paper_rate is None:
                continue
            if spec.name == "smolvla_libero" and env in LIBERO_SUITES:
                pooled_row = None
                if v11_df is not None:
                    pooled_row = _smolvla_suite_v11_row(v11_df, env, float(paper_rate))
                if pooled_row is None:
                    pooled_row = _smolvla_libero_suite_row(df, env, float(paper_rate))
                if pooled_row is not None:
                    rows.append(pooled_row)
                continue
            grp = df[(df["policy"] == spec.name) & (df["env"] == env)]
            if grp.empty:
                continue
            is_act_aloha = spec.name == "act" and "aloha" in str(env)
            if is_act_aloha and rerun_cell is not None:
                n = rerun_cell["n"]
                measured = rerun_cell["measured"]
                lo, hi = rerun_cell["lo"], rerun_cell["hi"]
            else:
                n = len(grp)
                k = int(grp["success"].sum())
                measured = k / n
                lo, hi = wilson_ci(k, n)
            rows.append(
                {
                    "policy": spec.name,
                    "env": env,
                    "paper": float(paper_rate),
                    "measured": measured,
                    "lo": lo,
                    "hi": hi,
                    "n": n,
                    "inside_mde": abs(measured - float(paper_rate)) < MDE_BAND,
                    "n_tasks_present": None,
                    "n_tasks_expected": None,
                }
            )
    return rows


def _smolvla_libero_suite_row(
    df: pd.DataFrame, suite: str, paper_rate: float
) -> dict[str, Any] | None:
    """Pool the per-task smolvla_libero cells of one LIBERO suite into one row.

    The suite spans up to 10 task slots: ``suite`` (task 0) and
    ``f"{suite}_t{t}"`` for ``t`` in 1..9. We pool whichever member cells are
    present in ``df`` via :func:`embodimetry.stats.pool_binomial` (Σk / Σn over
    disjoint task episode sets) so the measured point is a true 10-task rate,
    directly comparable to the 10-task paper average. Returns ``None`` only when
    no member cell exists at all. The returned ``n_tasks_present`` lets the
    figure annotate partial coverage (``< 10`` task slots present).
    """
    member_envs = [suite, *(f"{suite}_t{t}" for t in range(1, 10))]
    successes: list[int] = []
    n_trials: list[int] = []
    n_tasks_present = 0
    for member in member_envs:
        grp = df[(df["policy"] == "smolvla_libero") & (df["env"] == member)]
        if grp.empty:
            continue
        successes.append(int(grp["success"].sum()))
        n_trials.append(len(grp))
        n_tasks_present += 1
    if n_tasks_present == 0:
        return None
    pooled = pool_binomial(successes, n_trials)
    return {
        "policy": "smolvla_libero",
        "env": suite,
        "paper": paper_rate,
        "measured": pooled.success_rate,
        "lo": pooled.ci_low,
        "hi": pooled.ci_high,
        "n": pooled.n_episodes,
        "inside_mde": abs(pooled.success_rate - paper_rate) < MDE_BAND,
        "n_tasks_present": n_tasks_present,
        "n_tasks_expected": 10,
    }


def _smolvla_suite_v11_row(
    v11_df: pd.DataFrame, suite: str, paper_rate: float
) -> dict[str, Any] | None:
    """One v1.1 suite-average row with a cluster-robust t-CI and per-task rates.

    Requires ALL 10 task slots (``suite`` = task 0, ``{suite}_t1``..``_t9``)
    in ``v11_df`` — a partial suite must not masquerade as a suite average,
    so this returns ``None`` and lets the caller fall back to the
    coverage-annotated pooled path. The measured point is the equal-task
    suite mean; the interval is the one-sample 95% t-CI over the 10
    per-task rates (:func:`embodimetry.stats.cluster_mean_t_ci`, the
    task-as-sampling-unit house rule). ``inside_mde`` is False exactly when
    that t-CI excludes the published mean — the same task-level t test at
    α=0.05 the paper's suite table reports (all four suites exclude;
    SWEEP_V11 § 1) — NOT an episode-iid MDE-band check.
    """
    member_envs = [suite, *(f"{suite}_t{t}" for t in range(1, 10))]
    task_rates: list[float] = []
    n_total = 0
    for member in member_envs:
        grp = v11_df[(v11_df["policy"] == "smolvla_libero") & (v11_df["env"] == member)]
        if grp.empty:
            return None
        task_rates.append(float(grp["success"].mean()))
        n_total += len(grp)
    mean = float(np.mean(task_rates))
    lo, hi = cluster_mean_t_ci(task_rates)
    return {
        "policy": "smolvla_libero",
        "env": suite,
        "paper": paper_rate,
        "measured": mean,
        "lo": lo,
        "hi": hi,
        "n": n_total,
        "inside_mde": lo <= paper_rate <= hi,
        "n_tasks_present": 10,
        "n_tasks_expected": 10,
        "task_rates": task_rates,
        "ci_kind": "cluster_t",
    }


def replication_scatter(
    df: pd.DataFrame,
    *,
    style: Style,
    out_dir: Path,
    registry: PolicyRegistry | None = None,
    v11_df: pd.DataFrame | None = None,
) -> list[Path]:
    """Paper-reported vs measured success rate per cell.

    For every ``(policy, env)`` cell that has a published
    ``paper_reported_success`` rate in ``configs/policies.yaml``, plot
    one point at ``(paper, measured)``. Single-cell (N=250) points carry
    vertical Wilson 95% error bars and are greyed out when
    ``|measured - paper|`` is below the MDE band
    (``2 * wilson_halfwidth_at_p(0.5, 250) ~= 0.123``) — within the noise
    floor of the bench, "agrees with paper" is the right reading. Points
    outside the band are colored by policy.

    ACT × aloha_transfer_cube — the norm-fix story:

    - The MAIN act point plots at the norm-FIXED, Hub-default reading of
      **0.824 [0.772, 0.866]** (paper ≈ 0.50), sourced from the corrected
      rerun parquet (``_collect_replication_rows`` /
      ``_act_aloha_rerun_cell``); the canonical parquet carries the same
      corrected cell post-splice (#177). This is the architecture's true
      score once OUR normalization bug (#51) is fixed.
    - A small, explicitly-labeled "pre-fix (norm bug)" annotation at 0.016
      (``_ACT_PREFIX_BUG_POINT``) is overlaid with a faint connector to the
      main point so the jump our fix produced is visible. This is a
      self-caught harness bug, NOT an inference-settings story: the
      abandoned 0.764 "paper settings" point is gone.

    smolvla × libero_* — the v1.1 suite-average upgrade (SWEEP_V11 § 1/§ 9):

    - With ``v11_df`` (the all-10-task v1.1 parquet), each suite plots as
      the equal-task suite average with a **cluster-robust 95% t-CI over
      the 10 per-task rates** (task as sampling unit — episode-iid Wilson
      bars on pooled suite counts are vetoed at design effect 25–65×),
      annotated "(10-task suite avg)", with the 10 per-task rates overlaid
      as small muted dots so the within-suite heterogeneity (spread
      0.036–0.88) is visible behind each mean.
    - Without ``v11_df`` the suite row falls back to pooling whatever
      member cells exist in ``df`` ("(10-task pooled)" / "(partial: k/10
      tasks)") so coverage is never silently overstated.

    xvla rows are filtered upstream (deferred from leaderboard, PR #82).
    See ``configs/policies.yaml`` comments for per-cell citations (Zhao
    2023, Chi 2023 / Hub card, Shukor 2025, etc.).
    """
    df = _filter_leaderboard(df)
    if registry is None:
        registry = PolicyRegistry.from_yaml(Path("configs/policies.yaml"))
    rows = _collect_replication_rows(df, registry, v11_df=v11_df)

    s = apply_style(style)
    fig, ax = plt.subplots(figsize=s["figsize"])
    ax.plot([0, 1], [0, 1], linestyle="--", color=s["palette"]["muted"], linewidth=s["line_width"])

    color_map = _policy_color_map(style)
    label_fontsize = max(5, s["font_size"] - 4)
    # Labels are placed in a second pass after every marker is drawn: each
    # label tries a ladder of slots (above/below on its natural side, then
    # the mirrored side, then leader-line slots further out) and takes the
    # first whose renderer-measured extent stays inside the axes and hits
    # neither an earlier label nor any point's marker/whisker box — the v1
    # cluster near (0.5-0.65, 0.82) and the v1.1 suite points near x=0.9
    # collide under any fixed offset.
    # Limits are fixed BEFORE any pixel box is measured.
    ax.set_xlim(-0.02, 1.05)
    ax.set_ylim(-0.02, 1.05)
    placed_boxes: list[Any] = []
    obstacle_boxes: list[Any] = []
    label_queue: list[tuple[str, tuple[float, float]]] = []

    def _place_label(label: str, xy: tuple[float, float]) -> None:
        # The natural side keeps text growing toward the plot's interior
        # (points past mid-x get right-aligned text growing leftward), so
        # bbox_inches="tight" never crops a label off the right edge.
        def _side(extends_left: bool) -> tuple[int, str]:
            return (-6, "right") if extends_left else (6, "left")

        dx_a, ha_a = _side(xy[0] > 0.5)
        dx_b, ha_b = _side(xy[0] <= 0.5)
        candidates = (
            (dx_a, 5, "baseline", ha_a, False),
            (dx_a, -11, "top", ha_a, False),
            (dx_b, 5, "baseline", ha_b, False),
            (dx_b, -11, "top", ha_b, False),
            (dx_a, 20, "baseline", ha_a, True),
            (dx_a, -28, "top", ha_a, True),
        )
        # Slots far from the point need a thin leader line back to it.
        leader = {
            "arrowstyle": "-",
            "color": s["palette"]["muted"],
            "linewidth": 0.5,
            "alpha": 0.55,
            "shrinkA": 0,
            "shrinkB": 3,
        }

        def _try(cand: tuple[int, int, str, str, bool]) -> Any:
            dx, dy, va, ha, with_leader = cand
            return ax.annotate(
                label,
                xy=xy,
                xytext=(dx, dy),
                textcoords="offset points",
                ha=ha,
                va=va,
                fontsize=label_fontsize,
                color=s["fg"],
                alpha=0.75,
                arrowprops=leader if with_leader else None,
            )

        ax_box = ax.get_window_extent()
        for cand in candidates:
            ann = _try(cand)
            fig.canvas.draw()
            box = ann.get_window_extent()
            inside = box.x0 >= ax_box.x0 and box.x1 <= ax_box.x1 and box.y0 >= ax_box.y0
            if inside and not any(box.overlaps(b) for b in placed_boxes + obstacle_boxes):
                placed_boxes.append(box)
                return
            ann.remove()
        ann = _try(candidates[0])  # every slot collides: keep the default
        fig.canvas.draw()
        placed_boxes.append(ann.get_window_extent())

    def _plot_point(row: dict[str, Any], *, label: str, hollow: bool) -> None:
        paper = float(row["paper"])
        measured = float(row["measured"])
        err = [
            [max(0.0, measured - float(row["lo"]))],
            [max(0.0, float(row["hi"]) - measured)],
        ]
        inside_mde = bool(row.get("inside_mde", abs(measured - paper) < MDE_BAND))
        color = (
            s["palette"]["muted"]
            if inside_mde
            else color_map.get(str(row["policy"]), s["palette"]["muted"])
        )
        ax.errorbar(
            paper,
            measured,
            yerr=err,
            fmt="o",
            color=color,
            ecolor=color,
            markerfacecolor=("none" if hollow else color),
            markeredgecolor=color,
            capsize=3,
            markersize=5,
            elinewidth=s["line_width"],
        )
        # The whisker (lo..hi) plus marker, padded a few px, is a label
        # obstacle so no label sits on another point's error bar.
        x_px, y_lo_px = ax.transData.transform((paper, float(row["lo"])))
        _, y_hi_px = ax.transData.transform((paper, float(row["hi"])))
        obstacle_boxes.append(Bbox([[x_px - 5.0, y_lo_px - 5.0], [x_px + 5.0, y_hi_px + 5.0]]))
        label_queue.append((label, (paper, measured)))

    # Short display names: the full registry keys ("smolvla_libero/
    # libero_spatial (10-task suite avg)") overrun half the axis at the
    # paper figsize and exhaust every label slot; identity is already
    # carried by the policy color, so the four suite-average points carry
    # only their suite name and the caption states they are smolvla
    # 10-task suite averages.
    policy_short = {"smolvla_libero": "smolvla", "diffusion_policy": "diffusion"}
    env_short = {"aloha_transfer_cube": "aloha"}
    suite_short = {
        "libero_spatial": "spatial",
        "libero_object": "object",
        "libero_goal": "goal",
        "libero_10": "libero_10",
    }

    act_main_row: dict[str, Any] | None = None
    for row in rows:
        policy = str(row["policy"])
        env = str(row["env"])
        label = f"{policy_short.get(policy, policy)}/{env_short.get(env, env)}"
        # The ACT cell is the norm-FIXED 0.824 reading; flag it so the
        # overlaid pre-fix point reads as the bug we caught and fixed.
        if policy == "act" and "aloha" in env:
            label = f"{label} (norm-fixed)"
            act_main_row = row
        elif row.get("ci_kind") == "cluster_t":
            label = suite_short.get(env, env)
            # Per-task dots behind the suite mean: the within-suite
            # heterogeneity that makes the task the sampling unit.
            task_rates = [float(r) for r in row["task_rates"]]
            ax.scatter(
                [float(row["paper"])] * len(task_rates),
                task_rates,
                s=7,
                color=s["palette"]["muted"],
                alpha=0.55,
                zorder=2,
                linewidths=0,
            )
        elif policy == "smolvla_libero" and row.get("n_tasks_present") is not None:
            n_present = int(row["n_tasks_present"])
            n_expected = int(row.get("n_tasks_expected") or 10)
            if n_present >= n_expected:
                label = f"{label} (10-task pooled)"
            else:
                label = f"{label} (partial: {n_present}/{n_expected} tasks)"
        _plot_point(row, label=label, hollow=False)

    # Overlay the pre-fix (normalization bug) ACT point at 0.016 with a faint
    # connector up to the norm-fixed main point, so the figure shows the jump
    # our fix produced (0.016 -> 0.824) rather than leaving the buggy reading
    # off-chart. The abandoned 0.764 "paper settings" story is NOT plotted.
    if act_main_row is not None:
        ax.annotate(
            "",
            xy=(float(act_main_row["paper"]), float(act_main_row["measured"])),
            xytext=(_ACT_PREFIX_BUG_POINT["paper"], _ACT_PREFIX_BUG_POINT["measured"]),
            arrowprops={
                "arrowstyle": "->",
                "color": s["palette"]["muted"],
                "linewidth": s["line_width"],
                "alpha": 0.55,
                "linestyle": (0, (3, 2)),
            },
        )
        _plot_point(
            _ACT_PREFIX_BUG_POINT,
            label="act/aloha pre-fix (norm bug)",
            hollow=True,
        )

    # Second pass: every marker/whisker is on canvas, so labels can be
    # slotted around all of them, not just the ones drawn earlier.
    fig.canvas.draw()
    for label, xy in label_queue:
        _place_label(label, xy)

    ax.set_xlabel("paper-reported success")
    ax.set_ylabel("measured success")
    # Two-line title + generous pad; combined with the top-margin reserve
    # in subplots_adjust below this keeps the title from clipping at the
    # tight paper figsize (3.5x2.5in) where a one-line title overran the
    # saved bbox. tight_layout(rect=...) reserves the headroom.
    ax.set_title(
        "Paper-reported vs measured success\n"
        "grey = agrees with published; hollow = ACT pre-fix; dots = per-task",
        pad=8,
    )
    ax.grid(True, linestyle=":", alpha=0.25)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    _apply_bg(fig, s)
    # rect reserves the top 6% for the two-line title and a left strip for
    # the y-axis label so bbox_inches=tight in _save_all does not crop
    # either (the one-line title and the long y-label both clipped before).
    fig.tight_layout(rect=(0.04, 0.0, 1.0, 0.94))
    return _save_all(fig, "replication_scatter", style, out_dir)


# --------------------------------------------------------------------- #
# Figure 5 — v1.1 failure-taxonomy matrix (outlier cells)               #
# --------------------------------------------------------------------- #

# Canonical six-mode scheme, in docs/FAILURE_TAXONOMY.md heading order.
# The labeling CSV's canonical_label column must only use these (plus
# success_reference rows, which are excluded — they are not failures).
_TAXONOMY_MODES: tuple[str, ...] = (
    "trajectory_overshoot",
    "gripper_slip",
    "timeout",
    "wrong_object",
    "premature_release",
    "drift",
)
_TAXONOMY_MODE_LABELS: tuple[str, ...] = (
    "overshoot",
    "gripper\nslip",
    "timeout",
    "wrong\nobject",
    "premature\nrelease",
    "drift",
)
# The five v1.1 outlier cells, sweep-doc order (SWEEP_V11 § 10).
_TAXONOMY_CELLS: tuple[str, ...] = (
    "libero_spatial_t5",
    "libero_10",
    "libero_10_t4",
    "libero_10_t6",
    "libero_10_t7",
)
_TAXONOMY_CELL_LABELS: tuple[str, ...] = (
    "spatial_t5",
    "libero_10 (t0)",
    "libero_10_t4",
    "libero_10_t6",
    "libero_10_t7",
)
_TAXONOMY_CSV_DEFAULT: Path = (
    Path(__file__).resolve().parents[2] / "docs" / "assets" / "failure-taxonomy-labels-v11.csv"
)


def _taxonomy_counts(labels_csv: Path) -> pd.DataFrame:
    """Cells × canonical-mode count matrix from the v1.1 labeling CSV.

    Excludes ``success_reference`` rows (they are labeled successes, not
    failures) and raises on any other label outside the canonical six —
    silent drops would corrupt the counts the figure prints.
    """
    labels = pd.read_csv(labels_csv)
    failures = labels[labels["canonical_label"] != "success_reference"]
    unknown = set(failures["canonical_label"]) - set(_TAXONOMY_MODES)
    if unknown:
        raise ValueError(f"non-canonical labels in {labels_csv}: {sorted(unknown)}")
    counts = pd.DataFrame(0, index=list(_TAXONOMY_CELLS), columns=list(_TAXONOMY_MODES))
    grouped = failures.groupby(["env", "canonical_label"]).size().reset_index(name="n")
    for row in grouped.itertuples(index=False):
        env = str(row.env)
        mode = str(row.canonical_label)
        if env in counts.index:
            counts.loc[env, mode] = int(row.n)  # type: ignore[index,arg-type]
    return counts


def failure_taxonomy_v11(
    *,
    style: Style,
    out_dir: Path,
    labels_csv: Path | None = None,
) -> list[Path]:
    """v1.1 failure-taxonomy matrix: 5 outlier cells × canonical six modes.

    Counts of hand-labeled failed episodes (n=12 failures per cell,
    deterministic seed-round-robin sampling, labels joined on
    ``(policy, env, seed, episode_index)`` — SWEEP_V11 § 10) in each of
    the canonical six failure modes (``docs/FAILURE_TAXONOMY.md``).
    Modes with zero labeled episodes render as explicit dark-zero cells
    rather than being dropped — the matrix analogue of the v1 figure's
    empty-bar honesty. Counts are observational: at n=12 per cell no
    within- or cross-cell rate claim is supported.

    viridis, pinned to [0, 12] so color encodes the fraction of the
    cell's 12 labeled failures. Source:
    ``docs/assets/failure-taxonomy-labels-v11.csv``; computed at render,
    never hardcoded.
    """
    if labels_csv is None:
        labels_csv = _TAXONOMY_CSV_DEFAULT
    counts = _taxonomy_counts(labels_csv)
    s = apply_style(style)
    fig, ax = plt.subplots(figsize=s["figsize"])

    grid = counts.to_numpy(dtype=float)
    im = ax.imshow(grid, cmap="viridis", vmin=0.0, vmax=12.0, aspect="auto")

    ann_fs = max(6, s["font_size"] - 1)
    for r in range(grid.shape[0]):
        for c in range(grid.shape[1]):
            n = int(grid[r, c])
            # viridis is dark below ~60% of the ramp: flip ink there.
            txt_color = "#111111" if n > 7 else "#ffffff"
            ax.text(
                c,
                r,
                str(n),
                ha="center",
                va="center",
                fontsize=ann_fs,
                fontweight="bold" if n else "normal",
                color=txt_color,
                alpha=1.0 if n else 0.6,
            )

    ax.set_xticks(range(len(_TAXONOMY_MODES)))
    ax.set_xticklabels(_TAXONOMY_MODE_LABELS, fontsize=max(5, s["font_size"] - 3))
    ax.set_yticks(range(len(_TAXONOMY_CELLS)))
    ax.set_yticklabels(_TAXONOMY_CELL_LABELS, fontsize=max(6, s["font_size"] - 2))
    ax.tick_params(length=0)
    ax.set_xticks(np.arange(-0.5, len(_TAXONOMY_MODES), 1), minor=True)
    ax.set_yticks(np.arange(-0.5, len(_TAXONOMY_CELLS), 1), minor=True)
    ax.grid(which="minor", color=s["bg"] if s["bg"] != "transparent" else "white", linewidth=1.5)
    ax.tick_params(which="minor", length=0)

    ax.set_title(
        "v1.1 failure modes on the outlier cells\n(n=12 labeled failures per cell)",
        fontsize=s["font_size"],
        pad=6,
    )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("labeled failures (of 12)", fontsize=max(6, s["font_size"] - 2))
    cbar.ax.tick_params(labelsize=max(5, s["font_size"] - 3), length=0)

    _apply_bg(fig, s)
    fig.tight_layout(rect=(0.02, 0.0, 1.0, 0.94))
    return _save_all(fig, "failure_taxonomy_v11", style, out_dir)


# Public re-exports for the CLI.
FIGURES: dict[str, Any] = {
    "forest_plot": forest_plot,
    "act_norm_ablation_2x2": act_norm_ablation_2x2,
    "replication_scatter": replication_scatter,
    "failure_taxonomy_v11": failure_taxonomy_v11,
}

# Figures that render without the results parquet (no ``df`` argument).
# The render driver and CLI key off this set to pass the right kwargs.
PARQUET_FREE_FIGURES: frozenset[str] = frozenset({"act_norm_ablation_2x2", "failure_taxonomy_v11"})


def _as_style(name: str) -> Style:
    if name == "paper":
        return "paper"
    if name == "deck":
        return "deck"
    if name == "web":
        return "web"
    raise ValueError(f"unknown style {name!r}")
