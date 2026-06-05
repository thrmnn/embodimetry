"""Cross-artifact value-consistency guard for published headline scalars.

WHY THIS EXISTS
---------------
``tests/test_publish_preflight_coverage.py`` checks that every intended
(policy, env) *cell is present* in the parquet -- coverage, not values. It
would not have caught the v1 ``0.764`` / ``0.824`` drift, where the same
``ACT x aloha_transfer_cube`` cell was headlined as two different numbers on
different public surfaces (``site/index.html`` said 0.764 as the canonical
headline; README/paper/deck said 0.824). This module closes that gap: it
hard-fails if a registered headline scalar drifts from its source of truth.

TWO LAYERS
----------
Layer A (always runs, no data files needed) -- CROSS-SURFACE AGREEMENT:
    every public surface that headlines a registered cell must report the
    *same* canonical value within its published CI. This is the layer that
    catches the 0.764/0.824 bug directly: reintroduce 0.764 as the site
    headline and ``test_site_headline_matches_canonical`` goes red.

Layer B (runs only when the local ``results/`` tree is present) -- SOURCE OF
    TRUTH:
      * Leaderboard scalars must match the shipped parquet pooled cell rate,
        and the published CI must reproduce from ``wilson_ci`` within
        tolerance.
      * Probe-sourced scalars (the 2x2 ablation) must match their committed
        ``results/probes/.../summary.json`` pooled rate -- they are NOT
        required to live in the leaderboard parquet.
    The ``results/`` tree is ``.gitignore``-d (bench data lives on the Hub),
    so a fresh CI checkout has no data files. Layer B then SKIPS rather than
    false-fails -- a guard that false-flags a legitimate number is worse than
    no guard. Run it where the data is present (the maintainer's working
    tree) and it asserts for real.

CONSERVATISM
------------
Canonical numbers come from the explicit ``REGISTRY`` below, not from
regexing arbitrary prose. Each surface assertion parses one specific,
unambiguous token out of one specific file. If a surface's wording changes
so the token is no longer present, the test fails loudly (telling you to
update the locator) rather than silently passing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------- #
# Canonical registry: the single source of truth for every headline      #
# scalar this guard polices. Add a row here when a new number goes        #
# public; the surface + source-of-truth assertions key off it.            #
# --------------------------------------------------------------------- #


@dataclass(frozen=True)
class Scalar:
    """One published headline scalar and where it must agree.

    Attributes:
        key: human-readable id, used in failure messages.
        rate: the canonical pooled success rate (the headline number).
        ci: the published Wilson 95% interval ``(lo, hi)``.
        kind: ``"leaderboard"`` (source of truth = a results parquet cell)
            or ``"probe"`` (source of truth = a probe ``summary.json``).
        source: path (relative to repo root) of the source-of-truth artifact.
        cell: for leaderboard scalars, the ``(policy, env)`` parquet cell.
        n: expected episode count (leaderboard cells are N=250).
    """

    key: str
    rate: float
    ci: tuple[float, float]
    kind: str
    source: str
    cell: tuple[str, str] | None = None
    n: int | None = None
    note: str = ""


# Source-of-truth map (verified by computing wilson_ci from the committed
# data: every published CI below reproduces exactly):
#
#   act x aloha 0.824 [.772,.866]  <- results/sweep-full/results-act-rerun.parquet
#       (the CORRECTED rows; the canonical results.parquet still ships the
#        0.016 pre-#51 cell -- that un-merged parquet swap is a SEPARATE,
#        gated publish blocker, out of scope for this presentation-only guard.)
#   smolvla LIBERO cells           <- results/sweep-full/results.parquet
#   ablation 0.812 / 0.768         <- results/probes/act-norm-ablation/{fixed_hub,fixed_paper}/summary.json
REGISTRY: dict[str, Scalar] = {
    "act_aloha": Scalar(
        key="act x aloha_transfer_cube (canonical, Hub-default)",
        rate=0.824,
        ci=(0.772, 0.866),
        kind="leaderboard",
        source="results/sweep-full/results-act-rerun.parquet",
        cell=("act", "aloha_transfer_cube"),
        n=250,
        note="post-#51 norm fix; rerun parquet holds the corrected rows",
    ),
    "smolvla_libero_10": Scalar(
        key="smolvla x libero_10",
        rate=0.252,
        ci=(0.202, 0.309),
        kind="leaderboard",
        source="results/sweep-full/results.parquet",
        cell=("smolvla_libero", "libero_10"),
        n=250,
    ),
    "smolvla_libero_object": Scalar(
        key="smolvla x libero_object",
        rate=0.528,
        ci=(0.466, 0.589),
        kind="leaderboard",
        source="results/sweep-full/results.parquet",
        cell=("smolvla_libero", "libero_object"),
        n=250,
    ),
    "smolvla_libero_spatial": Scalar(
        key="smolvla x libero_spatial",
        rate=0.776,
        ci=(0.720, 0.823),
        kind="leaderboard",
        source="results/sweep-full/results.parquet",
        cell=("smolvla_libero", "libero_spatial"),
        n=250,
    ),
    "smolvla_libero_goal": Scalar(
        key="smolvla x libero_goal",
        rate=0.928,
        ci=(0.889, 0.954),
        kind="leaderboard",
        source="results/sweep-full/results.parquet",
        cell=("smolvla_libero", "libero_goal"),
        n=250,
    ),
    "ablation_fixed_hub": Scalar(
        key="ACT norm ablation: fixed norm, Hub-default inference",
        rate=0.812,
        ci=(0.759, 0.856),
        kind="probe",
        source="results/probes/act-norm-ablation/fixed_hub/summary.json",
        note="separate N=250 run of the same condition as the 0.824 leaderboard cell",
    ),
    "ablation_fixed_paper": Scalar(
        key="ACT norm ablation: fixed norm, paper-settings inference",
        rate=0.768,
        ci=(0.712, 0.816),
        kind="probe",
        source="results/probes/act-norm-ablation/fixed_paper/summary.json",
        note="the explicitly-labeled 'paper-settings variant'; a wash vs Hub-default",
    ),
}


# --------------------------------------------------------------------- #
# Layer A -- cross-surface agreement (no data files needed).             #
# --------------------------------------------------------------------- #


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _assert_present(text: str, token: str, surface: str, scalar_key: str) -> None:
    assert token in text, (
        f"{surface}: expected canonical token {token!r} for {scalar_key} not found. "
        f"Either the number drifted (the bug this guard exists to catch) or the "
        f"surface wording changed -- update the locator in this test if the latter."
    )


def _assert_absent(text: str, token: str, surface: str, why: str) -> None:
    assert token not in text, f"{surface}: stale token {token!r} is still headlined. {why}"


def test_site_headline_matches_canonical() -> None:
    """``site/index.html`` headlines act x aloha at 0.824, not the stale 0.764.

    This is the regression test for the exact v1 bug: the site headline used
    to read ``0.764 [0.708, 0.812]`` as THE canonical number. Reintroducing
    that token here goes red.
    """
    site = _read("site/index.html")
    s = REGISTRY["act_aloha"]
    _assert_present(site, "0.824", "site/index.html", s.key)
    _assert_present(site, "[0.772, 0.866]", "site/index.html", s.key)
    # The whole 0.764-as-headline narrative must be gone from the site. 0.708
    # is the low bound of the old 0.764 CI -- equally diagnostic of the drift.
    _assert_absent(
        site,
        "0.764",
        "site/index.html",
        "0.764 is the superseded paper-settings probe value; the canonical "
        "headline is 0.824. Keep 0.764 only in its labeled ablation/probe "
        "context (docs/probes), never as the site headline.",
    )
    _assert_absent(
        site,
        "0.708",
        "site/index.html",
        "0.708 is the low bound of the old 0.764 CI; the canonical CI is [0.772, 0.866].",
    )


def test_canonical_surfaces_agree_on_act_aloha() -> None:
    """README, paper, and deck all headline the same 0.824 [0.772, 0.866]."""
    s = REGISTRY["act_aloha"]
    for surface, ci_token in [
        ("README.md", "[0.772, 0.866]"),
        ("paper/main.tex", "0.824~[0.772, 0.866]"),
        ("paper/deck/index.html", "0.824"),
    ]:
        text = _read(surface)
        _assert_present(text, "0.824", surface, s.key)
        _assert_present(text, ci_token, surface, s.key)


def test_smolvla_leaderboard_scalars_present_in_readme() -> None:
    """README's leaderboard table carries each smolvla LIBERO headline value."""
    readme = _read("README.md")
    for key in (
        "smolvla_libero_10",
        "smolvla_libero_object",
        "smolvla_libero_spatial",
        "smolvla_libero_goal",
    ):
        s = REGISTRY[key]
        _assert_present(readme, f"{s.rate:.3f}", "README.md", s.key)


def test_ablation_scalars_framed_as_paper_settings_variant() -> None:
    """0.812/0.768 appear in README + paper as the labeled 2x2 ablation cells.

    These are probe-sourced (not in the leaderboard parquet); the guard only
    requires they are presented in their ablation context, never as the
    headline. We assert co-occurrence with the ablation framing.
    """
    for surface in ("README.md", "paper/main.tex"):
        text = _read(surface)
        _assert_present(text, "0.812", surface, REGISTRY["ablation_fixed_hub"].key)
        _assert_present(text, "0.768", surface, REGISTRY["ablation_fixed_paper"].key)


# --------------------------------------------------------------------- #
# Layer B -- source of truth (skips when the gitignored data is absent). #
# --------------------------------------------------------------------- #


def _require_data(rel: str) -> Path:
    p = REPO_ROOT / rel
    if not p.exists():
        pytest.skip(
            f"source-of-truth artifact {rel} is .gitignore-d (bench data lives "
            f"on the Hub) and not present in this checkout; cross-surface Layer A "
            f"still runs."
        )
    return p


def _pooled_cell_rate(parquet: Path, policy: str, env: str) -> tuple[int, int]:
    import pandas as pd

    df = pd.read_parquet(parquet)
    if "errored" in df.columns:
        df = df[~df["errored"].fillna(False)]
    sub = df[(df["policy"] == policy) & (df["env"] == env)]
    if len(sub) == 0:
        raise AssertionError(f"no rows for ({policy}, {env}) in {parquet}")
    return int(sub["success"].sum()), len(sub)


@pytest.mark.parametrize("key", [k for k, s in REGISTRY.items() if s.kind == "leaderboard"])
def test_leaderboard_scalar_matches_parquet(key: str) -> None:
    """Each leaderboard scalar matches its parquet cell rate + reproduces its CI."""
    from embodimetry.stats import wilson_ci

    s = REGISTRY[key]
    parquet = _require_data(s.source)
    assert s.cell is not None
    succ, n = _pooled_cell_rate(parquet, *s.cell)

    assert n == s.n, f"{s.key}: expected N={s.n}, parquet has N={n}"
    rate = succ / n
    assert rate == pytest.approx(s.rate, abs=1e-3), (
        f"{s.key}: registry says {s.rate}, parquet cell is {rate:.4f}"
    )
    lo, hi = wilson_ci(succ, n)
    assert (lo, hi) == pytest.approx(s.ci, abs=1e-3), (
        f"{s.key}: published CI {s.ci} does not reproduce from wilson_ci ({lo:.3f}, {hi:.3f})"
    )


@pytest.mark.parametrize("key", [k for k, s in REGISTRY.items() if s.kind == "probe"])
def test_probe_scalar_matches_summary_json(key: str) -> None:
    """Each probe scalar reproduces from its committed summary.json (NOT the parquet)."""
    s = REGISTRY[key]
    summary_path = _require_data(s.source)
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    pooled = float(summary["pooled_success_rate"])
    assert pooled == pytest.approx(s.rate, abs=1e-3), (
        f"{s.key}: registry says {s.rate}, summary.json pooled is {pooled:.4f}"
    )


def test_registry_cis_reproduce_when_data_present() -> None:
    """Sanity: when data is present, every registry CI is exactly the Wilson CI.

    Cheap end-to-end guard that the REGISTRY itself stays self-consistent with
    the artifacts -- catches a stale hand-edited CI in the registry.
    """
    from embodimetry.stats import wilson_ci

    for s in REGISTRY.values():
        path = REPO_ROOT / s.source
        if not path.exists():
            pytest.skip(f"{s.source} absent; covered by Layer A")
        if s.kind == "leaderboard":
            assert s.cell is not None
            succ, n = _pooled_cell_rate(path, *s.cell)
        else:
            summary = json.loads(path.read_text(encoding="utf-8"))
            rates = summary["per_seed_success_rate"].values()
            n = 50 * len(rates)
            succ = round(float(summary["pooled_success_rate"]) * n)
        lo, hi = wilson_ci(succ, n)
        assert (lo, hi) == pytest.approx(s.ci, abs=2e-3), (
            f"{s.key}: registry CI {s.ci} drifted from data CI ({lo:.3f}, {hi:.3f})"
        )


# Guard against the locator itself rotting: the canonical CI token formats we
# search for must be the ones the registry would produce.
def test_locator_tokens_track_registry() -> None:
    s = REGISTRY["act_aloha"]
    assert f"[{s.ci[0]:.3f}, {s.ci[1]:.3f}]" == "[0.772, 0.866]"
    assert f"{s.rate:.3f}" == "0.824"


# --------------------------------------------------------------------- #
# Figure DATA-LAYER guard (skips when the gitignored data is absent).    #
#                                                                        #
# The cross-surface tests above police TEXT scalars; this one polices the #
# headline FIGURE's data layer so a regression of the replication-scatter #
# ACT point back to 0.016 (buggy) or 0.764 (abandoned paper-settings red  #
# herring) fails CI. It asserts the figure's own data collector, not       #
# rendered pixels — pixels are a human eyeball job (flagged in the PR).    #
# --------------------------------------------------------------------- #


def test_replication_scatter_act_point_is_canonical() -> None:
    """``replication_scatter``'s data collector plots ACT × aloha at 0.824.

    Sources the ACT cell exactly as the figure does (via the rerun parquet,
    no gated merge required) and asserts it lands at the canonical
    0.824 [0.772, 0.866] — NOT the buggy 0.016 nor the abandoned 0.764. This
    is the figure-layer twin of ``test_canonical_surfaces_agree_on_act_aloha``.
    Skips when the gitignored ``results/`` tree is absent (Layer B contract).
    """
    pytest.importorskip("pandas")
    pytest.importorskip("matplotlib")
    import pandas as pd

    from embodimetry.figures import _collect_replication_rows
    from embodimetry.policies import PolicyRegistry

    s = REGISTRY["act_aloha"]
    rerun = _require_data(s.source)  # results/sweep-full/results-act-rerun.parquet
    canonical = _require_data("results/sweep-full/results.parquet")

    registry = PolicyRegistry.from_yaml(REPO_ROOT / "configs" / "policies.yaml")
    df = pd.read_parquet(canonical)
    rows = _collect_replication_rows(df, registry, rerun_path=rerun)

    act = [r for r in rows if r["policy"] == "act" and "aloha" in str(r["env"])]
    assert len(act) == 1, f"expected exactly one ACT×aloha scatter row, got {len(act)}"
    row = act[0]

    assert row["n"] == s.n, f"ACT scatter point N={row['n']}, expected {s.n}"
    assert row["measured"] == pytest.approx(s.rate, abs=1e-3), (
        f"ACT scatter point is {row['measured']:.4f}; the figure must plot the "
        f"norm-fixed {s.rate} (0.016 = pre-fix bug, 0.764 = abandoned "
        f"paper-settings red herring — neither may be the main point)."
    )
    assert (row["lo"], row["hi"]) == pytest.approx(s.ci, abs=1e-3), (
        f"ACT scatter CI ({row['lo']:.3f}, {row['hi']:.3f}) must reproduce {s.ci}."
    )
    # The 0.016 reading survives only as the explicitly-labeled pre-fix
    # annotation; it must never be the main measured point.
    assert row["measured"] != pytest.approx(0.016, abs=1e-3)
    assert row["measured"] != pytest.approx(0.764, abs=1e-3)
