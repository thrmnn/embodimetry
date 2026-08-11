"""Tests for ``embodimetry.figures`` and ``scripts/render_figures.py``.

Headless / fast: ``matplotlib.use("Agg")`` is set at import; no torch /
lerobot / gym deps. Synthetic data is generated per test so the suite
runs without ``results/sweep-full/results.parquet`` on disk.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

# Skip the whole module if matplotlib isn't installed: the figure-pipeline
# requires it but the bench's minimal CI install path ("fast" pytest job)
# does not pull matplotlib. Mirrors pytest.importorskip("lerobot") etc.
# elsewhere in this test tree.
matplotlib = pytest.importorskip("matplotlib")
matplotlib.use("Agg")

import pandas as pd  # noqa: E402  -- after pytest.importorskip("matplotlib") guard

from embodimetry import figures as fig_mod  # noqa: E402
from embodimetry.figures import (  # noqa: E402
    MDE_BAND,
    STYLES,
    act_norm_ablation_2x2,
    apply_style,
    failure_taxonomy_v11,
    forest_plot,
    replication_scatter,
)
from embodimetry.policies import PolicyRegistry, PolicySpec  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _synthetic_df() -> pd.DataFrame:
    """Two policies x two envs x 5 seeds x 50 ep (incl xvla, which must be filtered)."""
    rows: list[dict[str, object]] = []
    spec = [
        ("act", "aloha_transfer_cube", 0.20),
        ("smolvla_libero", "libero_spatial", 0.80),
        ("random", "pusht", 0.05),
        ("xvla_libero", "libero_spatial", 0.99),  # must be filtered out
    ]
    for policy, env, p in spec:
        for seed in range(5):
            for ep in range(50):
                rows.append(
                    {
                        "policy": policy,
                        "env": env,
                        "seed": seed,
                        "episode_index": ep,
                        "success": bool(((seed * 50 + ep) % 100) < int(p * 100)),
                    }
                )
    return pd.DataFrame(rows)


def _toy_registry() -> PolicyRegistry:
    specs = {
        "act": PolicySpec(
            name="act",
            is_baseline=False,
            env_compat=("aloha_transfer_cube",),
            repo_id="x",
            revision_sha="y",
            paper_reported_success={"aloha_transfer_cube": 0.50},
        ),
        "smolvla_libero": PolicySpec(
            name="smolvla_libero",
            is_baseline=False,
            env_compat=("libero_spatial",),
            repo_id="x",
            revision_sha="y",
            paper_reported_success={"libero_spatial": 0.90},
        ),
    }
    return PolicyRegistry(specs)


def test_apply_style_returns_copy_not_reference() -> None:
    s = apply_style("paper")
    s["palette"]["ok"] = "#ff00ff"
    s["font_size"] = 999
    again = apply_style("paper")
    assert again["palette"]["ok"] != "#ff00ff"
    assert again["font_size"] != 999


def test_styles_have_required_keys() -> None:
    required = {"figsize", "font_family", "palette", "bg", "dpi", "formats"}
    required_palette = {"ok", "warm", "fail", "muted"}
    for name, s in STYLES.items():
        missing = required - set(s)
        assert not missing, f"{name} missing keys {missing}"
        palette_missing = required_palette - set(s["palette"])
        assert not palette_missing, f"{name}.palette missing {palette_missing}"


def test_forest_plot_produces_file_per_format(tmp_path: Path) -> None:
    df = _synthetic_df()
    for style in STYLES:
        paths = forest_plot(df, style=style, out_dir=tmp_path)
        assert len(paths) == len(STYLES[style]["formats"])
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0
            assert p.parent == tmp_path / style


def test_act_probe_bar_is_retired() -> None:
    # The probe bar hardcoded the abandoned "inference settings are the
    # load-bearing variable" framing; it must stay out of the registry so
    # `make paper-figures` cannot regenerate a paper-contradicting asset.
    assert "act_probe_bar" not in fig_mod.FIGURES
    assert not hasattr(fig_mod, "act_probe_bar")


def test_act_norm_ablation_2x2_produces_file_per_format(tmp_path: Path) -> None:
    for style in STYLES:
        paths = act_norm_ablation_2x2(style=style, out_dir=tmp_path)
        assert len(paths) == len(STYLES[style]["formats"])
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0
            assert p.parent == tmp_path / style
            assert p.stem == "act_norm_ablation"


def test_act_norm_ablation_2x2_uses_canonical_cells() -> None:
    cells = fig_mod._ACT_NORM_ABLATION
    assert cells[(0, 0)]["rate"] == pytest.approx(0.016)  # buggy + hub
    assert cells[(0, 1)]["rate"] == pytest.approx(0.016)  # buggy + paper
    assert cells[(1, 0)]["rate"] == pytest.approx(0.812)  # fixed + hub
    assert cells[(1, 1)]["rate"] == pytest.approx(0.768)  # fixed + paper
    assert cells[(1, 0)]["ci"] == (0.759, 0.856)
    assert cells[(1, 1)]["ci"] == (0.712, 0.816)


def test_replication_scatter_filters_xvla(tmp_path: Path) -> None:
    df = _synthetic_df()
    assert (df["policy"] == "xvla_libero").any()
    rows = fig_mod._collect_replication_rows(fig_mod._filter_leaderboard(df), _toy_registry())
    assert all(r["policy"] != "xvla_libero" for r in rows)
    paths = replication_scatter(df, style="web", out_dir=tmp_path, registry=_toy_registry())
    assert all(p.exists() for p in paths)


def test_replication_scatter_greyscale_for_inside_MDE() -> None:
    rows = [
        {
            "policy": "act",
            "env": "e",
            "paper": 0.50,
            "measured": 0.55,
            "lo": 0.5,
            "hi": 0.6,
            "n": 250,
        },
        {
            "policy": "act",
            "env": "e",
            "paper": 0.50,
            "measured": 0.95,
            "lo": 0.92,
            "hi": 0.97,
            "n": 250,
        },
    ]
    assert abs(rows[0]["measured"] - rows[0]["paper"]) < MDE_BAND
    assert abs(rows[1]["measured"] - rows[1]["paper"]) >= MDE_BAND


def _smolvla_registry() -> PolicyRegistry:
    """Registry whose smolvla_libero paper rate keys on the suite name."""
    return PolicyRegistry(
        {
            "smolvla_libero": PolicySpec(
                name="smolvla_libero",
                is_baseline=False,
                env_compat=("libero_spatial",),
                repo_id="x",
                revision_sha="y",
                paper_reported_success={"libero_spatial": 0.90},
            ),
        }
    )


def _smolvla_cell(env: str, n_success: int, n_total: int) -> list[dict[str, object]]:
    """Per-episode rows for one smolvla_libero task cell with exactly n_success hits."""
    return [
        {
            "policy": "smolvla_libero",
            "env": env,
            "seed": ep // 50,
            "episode_index": ep % 50,
            "success": ep < n_success,
        }
        for ep in range(n_total)
    ]


def test_collect_replication_pools_all_10_libero_tasks() -> None:
    rows_data: list[dict[str, object]] = []
    # Task 0 rate is deliberately distinct from the pooled rate: task 0 is
    # 5/50 = 0.10, tasks 1-9 are 45/50 = 0.90 each -> pooled = 410/500 = 0.82.
    rows_data += _smolvla_cell("libero_spatial", n_success=5, n_total=50)
    for t in range(1, 10):
        rows_data += _smolvla_cell(f"libero_spatial_t{t}", n_success=45, n_total=50)
    df = pd.DataFrame(rows_data)

    rows = fig_mod._collect_replication_rows(df, _smolvla_registry())
    assert len(rows) == 1
    row = rows[0]

    total_k = sum(int(r["success"]) for r in rows_data)
    total_n = len(rows_data)
    assert total_n == 500
    assert row["n"] == total_n
    assert row["measured"] == pytest.approx(total_k / total_n)
    # The pooled rate must differ from the task-0-only rate (the old bug).
    task0_rate = 5 / 50
    assert abs(row["measured"] - task0_rate) > 0.5
    assert row["n_tasks_present"] == 10
    assert row["n_tasks_expected"] == 10


def test_collect_replication_partial_libero_coverage() -> None:
    rows_data: list[dict[str, object]] = []
    rows_data += _smolvla_cell("libero_spatial", n_success=5, n_total=50)
    rows_data += _smolvla_cell("libero_spatial_t1", n_success=45, n_total=50)
    rows_data += _smolvla_cell("libero_spatial_t2", n_success=45, n_total=50)
    df = pd.DataFrame(rows_data)

    rows = fig_mod._collect_replication_rows(df, _smolvla_registry())
    assert len(rows) == 1
    row = rows[0]
    assert row["n_tasks_present"] == 3
    assert row["n_tasks_expected"] == 10
    assert row["n"] == 150
    assert row["measured"] == pytest.approx((5 + 45 + 45) / 150)


def test_collect_replication_non_smolvla_cell_unchanged() -> None:
    df = pd.DataFrame(
        [
            {
                "policy": "diffusion_policy",
                "env": "pusht",
                "seed": ep // 50,
                "episode_index": ep % 50,
                "success": ep < 100,
            }
            for ep in range(250)
        ]
    )
    registry = PolicyRegistry(
        {
            "diffusion_policy": PolicySpec(
                name="diffusion_policy",
                is_baseline=False,
                env_compat=("pusht",),
                repo_id="x",
                revision_sha="y",
                paper_reported_success={"pusht": 0.62},
            ),
        }
    )
    rows = fig_mod._collect_replication_rows(df, registry)
    assert len(rows) == 1
    row = rows[0]
    assert row["policy"] == "diffusion_policy"
    assert row["env"] == "pusht"
    assert row["n"] == 250
    assert row["measured"] == pytest.approx(100 / 250)
    # The new branch must not attach coverage fields to non-smolvla rows.
    assert row["n_tasks_present"] is None
    assert row["n_tasks_expected"] is None


def test_cli_renders_all_figures_with_defaults(tmp_path: Path) -> None:
    df = _synthetic_df()
    results_path = tmp_path / "results.parquet"
    df.to_parquet(results_path)
    out_dir = tmp_path / "figures"
    env = {"PYTHONPATH": str(_REPO_ROOT / "src")}
    result = subprocess.run(
        [
            sys.executable,
            str(_REPO_ROOT / "scripts" / "render_figures.py"),
            "--results",
            str(results_path),
            "--out-dir",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env={**__import__("os").environ, **env},
    )
    fig_names = (
        "forest_plot",
        "act_norm_ablation",
        "replication_scatter",
        "failure_taxonomy_v11",
    )
    expected: list[Path] = []
    for fig_name in fig_names:
        for style, style_dict in STYLES.items():
            for ext in style_dict["formats"]:
                expected.append(out_dir / style / f"{fig_name}.{ext}")
    for p in expected:
        assert p.exists(), f"missing: {p}\nstdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        assert p.stat().st_size > 0
    # 4 figs x (paper(2) + deck(1) + web(1)) = 16 files
    assert len(expected) == len(fig_names) * 4


def _v11_suite_df(task_rates: list[float], suite: str = "libero_spatial") -> pd.DataFrame:
    """All-10-task v1.1-shaped frame with exact per-task success rates."""
    assert len(task_rates) == 10
    rows: list[dict[str, object]] = []
    for t, rate in enumerate(task_rates):
        env = suite if t == 0 else f"{suite}_t{t}"
        rows += _smolvla_cell(env, n_success=round(rate * 50), n_total=50)
    return pd.DataFrame(rows)


def test_smolvla_suite_v11_row_uses_cluster_t_ci() -> None:
    scipy_stats = pytest.importorskip("scipy.stats")
    task_rates = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.4, 0.6]
    df = _v11_suite_df(task_rates)
    row = fig_mod._smolvla_suite_v11_row(df, "libero_spatial", 0.90)
    assert row is not None
    import numpy as np

    arr = np.asarray(task_rates)
    mean = arr.mean()
    hw = float(scipy_stats.t.ppf(0.975, 9)) * arr.std(ddof=1) / np.sqrt(10)
    assert row["measured"] == pytest.approx(mean)
    assert row["lo"] == pytest.approx(mean - hw)
    assert row["hi"] == pytest.approx(mean + hw)
    assert row["task_rates"] == pytest.approx(task_rates)
    assert row["ci_kind"] == "cluster_t"
    assert row["n"] == 500
    # The t-CI excludes the published 0.90, so the point must NOT grey out.
    assert row["hi"] < 0.90
    assert row["inside_mde"] is False


def test_smolvla_suite_v11_row_rejects_partial_suite() -> None:
    df = _v11_suite_df([0.5] * 10)
    partial = df[df["env"] != "libero_spatial_t7"]
    assert fig_mod._smolvla_suite_v11_row(partial, "libero_spatial", 0.90) is None


def test_collect_replication_rows_prefers_v11_df() -> None:
    # v1-shaped df: task-0 cell only, at a rate far from the v11 suite mean.
    v1_df = pd.DataFrame(_smolvla_cell("libero_spatial", n_success=5, n_total=50))
    v11_df = _v11_suite_df([0.6] * 10)
    rows = fig_mod._collect_replication_rows(v1_df, _smolvla_registry(), v11_df=v11_df)
    assert len(rows) == 1
    assert rows[0]["ci_kind"] == "cluster_t"
    assert rows[0]["measured"] == pytest.approx(0.6)


def test_replication_scatter_renders_with_v11_df(tmp_path: Path) -> None:
    v1_df = pd.DataFrame(_smolvla_cell("libero_spatial", n_success=5, n_total=50))
    v11_df = _v11_suite_df([0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.4, 0.6])
    paths = replication_scatter(
        v1_df, style="web", out_dir=tmp_path, registry=_smolvla_registry(), v11_df=v11_df
    )
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)


def _synthetic_taxonomy_csv(tmp_path: Path) -> Path:
    lines = ["labeled_by,date_iso,artifact,policy,env,observed_mode,canonical_label,notes"]
    cells_labels = [
        ("libero_spatial_t5", ["premature_release"] * 7 + ["gripper_slip"] * 4 + ["wrong_object"]),
        ("libero_10", ["timeout"] * 12),
        ("libero_10_t4", ["gripper_slip"] * 4 + ["timeout"] * 5 + ["premature_release"] * 3),
        ("libero_10_t6", ["timeout"] * 10 + ["wrong_object"] * 2),
        ("libero_10_t7", ["timeout"] * 11 + ["wrong_object"]),
    ]
    for env, labels in cells_labels:
        for i, label in enumerate(labels):
            lines.append(f"x,2026-08-10,v{i}.mp4,smolvla_libero,{env},obs,{label},note")
    lines.append("x,2026-08-10,s.mp4,smolvla_libero,libero_spatial_t5,ok,success_reference,note")
    path = tmp_path / "labels.csv"
    path.write_text("\n".join(lines) + "\n")
    return path


def test_taxonomy_counts_excludes_success_reference(tmp_path: Path) -> None:
    counts = fig_mod._taxonomy_counts(_synthetic_taxonomy_csv(tmp_path))
    assert counts.loc["libero_spatial_t5", "premature_release"] == 7
    assert counts.loc["libero_spatial_t5", "gripper_slip"] == 4
    assert counts.loc["libero_10", "timeout"] == 12
    # Empty-mode honesty: zero cells exist rather than being dropped.
    assert counts.loc["libero_10", "drift"] == 0
    assert (counts.sum(axis=1) == 12).all()


def test_taxonomy_counts_raises_on_unknown_label(tmp_path: Path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "labeled_by,date_iso,artifact,policy,env,observed_mode,canonical_label,notes\n"
        "x,2026-08-10,v.mp4,smolvla_libero,libero_10,obs,made_up_mode,note\n"
    )
    with pytest.raises(ValueError, match="made_up_mode"):
        fig_mod._taxonomy_counts(path)


def test_failure_taxonomy_v11_produces_file_per_format(tmp_path: Path) -> None:
    csv_path = _synthetic_taxonomy_csv(tmp_path)
    for style in STYLES:
        paths = failure_taxonomy_v11(style=style, out_dir=tmp_path, labels_csv=csv_path)
        assert len(paths) == len(STYLES[style]["formats"])
        for p in paths:
            assert p.exists()
            assert p.stat().st_size > 0
            assert p.stem == "failure_taxonomy_v11"


def test_failure_taxonomy_v11_renders_from_committed_csv(tmp_path: Path) -> None:
    committed = _REPO_ROOT / "docs" / "assets" / "failure-taxonomy-labels-v11.csv"
    assert committed.exists()
    counts = fig_mod._taxonomy_counts(committed)
    # 62 rows = 60 failures + 2 success references (excluded).
    assert int(counts.to_numpy().sum()) == 60
    assert (counts.sum(axis=1) == 12).all()
    paths = failure_taxonomy_v11(style="paper", out_dir=tmp_path, labels_csv=committed)
    assert all(p.exists() for p in paths)
