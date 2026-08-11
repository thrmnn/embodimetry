"""Tests for ``scripts/rerun_post51_cells.py``.

Builds a synthetic 5250-row canonical parquet with the real stale-cell
layout (diffusion_policy×pusht at three pre-#51 shas, random×libero_spatial
seeds 0-3 at ``d9cdb28a``, seed 4 kept at the fix sha) and asserts:

* ``prepare`` backs up parquet + manifest, deletes exactly the 325 stale
  rows, is idempotent, never touches fresh rows, and aborts on a
  stale/fresh mix inside one cell;
* ``finalize`` passes only when every target cell is re-filled post-#51
  at full shape, and archives the re-run manifest + restores the
  original.

Ancestry is monkeypatched via the module-level ``_is_post_fix`` injection
point (same pattern as ``run_sweep._run_subprocess``). No torch, no git,
no network: pure pandas fixtures on tmp_path.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest
from scripts import rerun_post51_cells as mod

from embodimetry.checkpointing import RESULT_SCHEMA, _atomic_write_parquet, load_results

FRESH_SHA = "feedc0de" * 5  # stand-in for HEAD at re-run time

# --------------------------------------------------------------------- #
# Fixture builders                                                      #
# --------------------------------------------------------------------- #


def _row(
    *,
    policy: str,
    env: str,
    seed: int,
    episode_index: int,
    code_sha: str,
) -> dict:
    return {
        "policy": policy,
        "env": env,
        "seed": seed,
        "episode_index": episode_index,
        "success": False,
        "return_": 0.0,
        "n_steps": 10,
        "wallclock_s": 0.05,
        "video_sha256": f"{policy}_{env}_{seed}_{episode_index}",
        "code_sha": code_sha,
        "lerobot_version": "0.5.1",
        "timestamp_utc": "2026-05-22T00:00:00+00:00",
        "errored": False,
        "eval_run_id": "",
    }


def _cell_rows(policy: str, env: str, seed: int, n: int, sha: str) -> list[dict]:
    return [
        _row(policy=policy, env=env, seed=seed, episode_index=i, code_sha=sha) for i in range(n)
    ]


_DP_SHAS = sorted(mod.DP_STALE_SHAS)


def _canonical_df() -> pd.DataFrame:
    """5250 rows mirroring the real layout of results/sweep-full/results.parquet."""
    rows: list[dict] = []
    # diffusion_policy×pusht: 5 seeds × 25 eps across the three stale shas.
    for seed in range(5):
        rows += _cell_rows("diffusion_policy", "pusht", seed, 25, _DP_SHAS[seed % 3])
    # random×libero_spatial: seeds 0-3 stale, seed 4 at the fix sha (kept).
    for seed in range(4):
        rows += _cell_rows("random", "libero_spatial", seed, 50, next(iter(mod.RANDOM_STALE_SHAS)))
    rows += _cell_rows("random", "libero_spatial", 4, 50, mod.FIX_SHA)
    # Filler for the remaining 4875 rows: a baseline (no_op, ancestry-exempt)
    # and a pretrained policy (act, must be post-#51 for finalize to pass).
    for seed in range(5):
        rows += _cell_rows("act", "aloha_transfer_cube", seed, 50, FRESH_SHA)
    for seed in range(5):
        rows += _cell_rows("no_op", "libero_object", seed, 925, "ancient" + "0" * 33)
    df = pd.DataFrame(rows, columns=list(RESULT_SCHEMA))
    assert len(df) == mod.EXPECTED_TOTAL_ROWS
    return df


@pytest.fixture
def sweep_dir(tmp_path, monkeypatch):
    d = tmp_path / "sweep-full"
    d.mkdir()
    _atomic_write_parquet(d / mod.CANONICAL_NAME, _canonical_df())
    (d / mod.MANIFEST_NAME).write_text(json.dumps({"original": True}))
    monkeypatch.setattr(mod, "_is_post_fix", lambda sha: sha in {FRESH_SHA, mod.FIX_SHA})
    return d


def _refill_targets(d, *, skip: tuple[str, str, int] | None = None, sha: str = FRESH_SHA) -> None:
    """Simulate run_sweep re-filling the 9 target cells at HEAD."""
    df = load_results(d / mod.CANONICAL_NAME)
    new: list[dict] = []
    for cell in mod.TARGET_CELLS:
        if (cell.policy, cell.env, cell.seed) == skip:
            continue
        new += _cell_rows(cell.policy, cell.env, cell.seed, cell.n_episodes, sha)
    merged = pd.concat([df, pd.DataFrame(new, columns=list(RESULT_SCHEMA))], ignore_index=True)
    _atomic_write_parquet(d / mod.CANONICAL_NAME, merged)


def _backups(d, pattern: str) -> list:
    return sorted(d.glob(pattern))


# --------------------------------------------------------------------- #
# prepare                                                               #
# --------------------------------------------------------------------- #


def test_prepare_deletes_stale_rows_and_backs_up(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0

    df = load_results(sweep_dir / mod.CANONICAL_NAME)
    assert len(df) == mod.EXPECTED_TOTAL_ROWS - 325
    assert ((df["policy"] == "diffusion_policy") & (df["env"] == "pusht")).sum() == 0
    keep = df[(df["policy"] == "random") & (df["env"] == "libero_spatial")]
    assert len(keep) == 50
    assert set(keep["seed"]) == {4}
    assert set(keep["code_sha"]) == {mod.FIX_SHA}

    pq_baks = _backups(sweep_dir, "results.pre_rerun_post51-*.bak.parquet")
    assert len(pq_baks) == 1
    assert len(load_results(pq_baks[0])) == mod.EXPECTED_TOTAL_ROWS
    assert len(_backups(sweep_dir, "sweep_manifest.pre_rerun_post51-*.bak.json")) == 1


def test_prepare_dry_run_writes_nothing(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir), "--dry-run"]) == 0
    assert len(load_results(sweep_dir / mod.CANONICAL_NAME)) == mod.EXPECTED_TOTAL_ROWS
    assert _backups(sweep_dir, "results.pre_rerun_post51-*.bak.parquet") == []


def test_prepare_is_idempotent(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    assert len(load_results(sweep_dir / mod.CANONICAL_NAME)) == mod.EXPECTED_TOTAL_ROWS - 325
    # The no-op second run must not stack another backup.
    assert len(_backups(sweep_dir, "results.pre_rerun_post51-*.bak.parquet")) == 1


def test_prepare_never_touches_fresh_partial_rows(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    # Aborted re-run: one cell partially re-filled at HEAD.
    df = load_results(sweep_dir / mod.CANONICAL_NAME)
    partial = pd.DataFrame(
        _cell_rows("diffusion_policy", "pusht", 0, 10, FRESH_SHA), columns=list(RESULT_SCHEMA)
    )
    _atomic_write_parquet(
        sweep_dir / mod.CANONICAL_NAME, pd.concat([df, partial], ignore_index=True)
    )

    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    df2 = load_results(sweep_dir / mod.CANONICAL_NAME)
    fresh = df2[(df2["policy"] == "diffusion_policy") & (df2["env"] == "pusht")]
    assert len(fresh) == 10
    assert set(fresh["code_sha"]) == {FRESH_SHA}


def test_prepare_aborts_on_stale_fresh_mix(sweep_dir):
    df = load_results(sweep_dir / mod.CANONICAL_NAME)
    mask = (df["policy"] == "diffusion_policy") & (df["env"] == "pusht") & (df["seed"] == 2)
    df.loc[df[mask].index[:5], "code_sha"] = FRESH_SHA
    _atomic_write_parquet(sweep_dir / mod.CANONICAL_NAME, df)

    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 1
    # Nothing deleted, nothing backed up.
    assert len(load_results(sweep_dir / mod.CANONICAL_NAME)) == mod.EXPECTED_TOTAL_ROWS
    assert _backups(sweep_dir, "results.pre_rerun_post51-*.bak.parquet") == []


# --------------------------------------------------------------------- #
# finalize                                                              #
# --------------------------------------------------------------------- #


def test_finalize_passes_and_restores_manifest(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    _refill_targets(sweep_dir)
    # run_sweep clobbers the manifest with the re-run's own.
    (sweep_dir / mod.MANIFEST_NAME).write_text(json.dumps({"rerun": True}))

    assert mod.main(["finalize", "--sweep-dir", str(sweep_dir)]) == 0
    assert len(load_results(sweep_dir / mod.CANONICAL_NAME)) == mod.EXPECTED_TOTAL_ROWS
    restored = json.loads((sweep_dir / mod.MANIFEST_NAME).read_text())
    assert restored == {"original": True}
    archives = _backups(sweep_dir, "sweep_manifest.rerun_post51-*.json")
    assert len(archives) == 1
    assert json.loads(archives[0].read_text()) == {"rerun": True}


def test_finalize_fails_on_missing_cell(sweep_dir):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    _refill_targets(sweep_dir, skip=("random", "libero_spatial", 2))
    (sweep_dir / mod.MANIFEST_NAME).write_text(json.dumps({"rerun": True}))

    assert mod.main(["finalize", "--sweep-dir", str(sweep_dir)]) == 1
    # Manifest must NOT be restored on a failed verification.
    assert json.loads((sweep_dir / mod.MANIFEST_NAME).read_text()) == {"rerun": True}


def test_finalize_fails_on_pre51_pretrained_rows(sweep_dir, monkeypatch):
    assert mod.main(["prepare", "--sweep-dir", str(sweep_dir)]) == 0
    _refill_targets(sweep_dir)
    # HEAD-at-rerun turns out NOT to contain the #51 fix.
    monkeypatch.setattr(mod, "_is_post_fix", lambda sha: sha == mod.FIX_SHA)
    assert mod.main(["finalize", "--sweep-dir", str(sweep_dir)]) == 1


def test_finalize_fails_before_prepare_ran(sweep_dir):
    # Stale rows still present: dp cells carry pre-#51 shas.
    assert mod.main(["finalize", "--sweep-dir", str(sweep_dir)]) == 1
