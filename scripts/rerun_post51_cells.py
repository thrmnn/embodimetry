#!/usr/bin/env python3
"""Prepare/finalize the targeted post-#51 re-run of the last pre-#51 pretrained rows.

Provenance / why this exists
============================
The #51 normalization fix landed at code_sha ``7361d962``. The act×aloha
rows were already replaced (``scripts/merge_corrected_act_rows.py``), but
two cells in the canonical ``results/sweep-full/results.parquet`` still
carry pre-#51 ``eval.py`` rows:

* ``diffusion_policy×pusht`` — 125 rows (5 seeds × 25 episodes, the
  auto-downscoped shape) at code_shas ``38ae2cbf`` / ``a581b971`` /
  ``ae6002b7``. These are the ONLY remaining pre-#51 *pretrained* rows.
* ``random×libero_spatial`` seeds 0–3 — 200 rows at ``d9cdb28a``; seed 4
  already ran at ``7361d962`` and is KEPT.

Replacing them makes every pretrained row post-#51, strengthening the
publish-override basis (see ``docs/CODE_SHA_INTEGRITY_AUDIT.md``).

Mechanics (delete-then-run)
===========================
``embodimetry.checkpointing.append_cell_rows`` rejects duplicate
``(policy, env, seed, episode_index)`` keys, so the stale rows must be
deleted BEFORE the re-run; ``run_sweep``'s ``plan_resume`` then sees the
9 target cells as pending and re-fills them at HEAD. The operator flow
is a three-stage chain (each stage independently re-runnable)::

    python scripts/rerun_post51_cells.py prepare            # backup + delete stale rows
    python scripts/run_sweep.py --config configs/sweep_rerun_post51.yaml --resume
    python scripts/rerun_post51_cells.py finalize           # verify + restore manifest

``prepare`` is idempotent: it deletes only rows whose ``code_sha`` is in
the per-cell stale set, so fresh rows written by an aborted re-run are
never touched and a second ``prepare`` is a no-op. It takes a timestamped
backup of the parquet AND ``sweep_manifest.json`` (which ``run_sweep``
will overwrite) before the first deletion.

``finalize`` verifies row counts / cell shapes / single-``code_sha``
cells / post-#51 ancestry for every pretrained row, then archives the
re-run's manifest and RESTORES the original full-sweep manifest (the
publish preflight derives its required coverage from the manifest's
``config_path`` — leaving the 20-cell re-run manifest in place would
misdescribe the published dataset).

Rollback at any point::

    cp results/sweep-full/results.pre_rerun_post51-<TS>.bak.parquet \
       results/sweep-full/results.parquet
    cp results/sweep-full/sweep_manifest.pre_rerun_post51-<TS>.bak.json \
       results/sweep-full/sweep_manifest.json

Like ``merge_corrected_act_rows.py`` this is tracked, reviewable tooling
operating on gitignored data; ``--sweep-dir`` lets the mechanics be
rehearsed on a copy of the sweep directory first.
"""

from __future__ import annotations

import argparse
import datetime as dt
import logging
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from embodimetry.checkpointing import _atomic_write_parquet, load_results
from embodimetry.policies import PolicyRegistry

logger = logging.getLogger("rerun-post51-cells")

# --------------------------------------------------------------------- #
# Constants                                                             #
# --------------------------------------------------------------------- #

_REPO_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_SWEEP_DIR = Path("results/sweep-full")
CANONICAL_NAME = "results.parquet"
MANIFEST_NAME = "sweep_manifest.json"
RERUN_CONFIG = Path("configs/sweep_rerun_post51.yaml")
POLICIES_YAML = _REPO_ROOT / "configs" / "policies.yaml"

# The #51 fix commit ("fix(eval): correct act legacy-normalization
# recovery"). A row is post-#51 iff this commit is an ancestor of its
# code_sha.
FIX_SHA = "7361d962f8d429fd61d299ad62a603b50b90b0cb"

# Stale pre-#51 code_shas carried by the diffusion_policy×pusht cell
# (seed 0 / seeds 1-3 / seed 4 respectively; the original sweep resumed
# across three HEADs).
DP_STALE_SHAS = frozenset(
    {
        "38ae2cbf76d8a0144df826e64d92c09feb14a85a",
        "a581b9712561d2f5fbc3d3da354332d933bf0f57",
        "ae6002b7cd7a9cc57dad11c8b71ca31b83d1bcba",
    }
)
# Stale pre-#51 code_sha carried by random×libero_spatial seeds 0-3.
RANDOM_STALE_SHAS = frozenset({"d9cdb28ab16c63534e5c3207b8466060739692c5"})

# Canonical parquet shape before AND after the re-run: the operation
# replaces rows in place, never changes counts.
EXPECTED_TOTAL_ROWS = 5250

_BACKUP_STEM = "pre_rerun_post51"


@dataclass(frozen=True)
class TargetCell:
    """One (policy, env, seed) cell whose stale rows get replaced."""

    policy: str
    env: str
    seed: int
    n_episodes: int
    stale_shas: frozenset[str]

    @property
    def display(self) -> str:
        return f"{self.policy}/{self.env}/seed{self.seed}"


TARGET_CELLS: tuple[TargetCell, ...] = tuple(
    [TargetCell("diffusion_policy", "pusht", s, 25, DP_STALE_SHAS) for s in range(5)]
    + [TargetCell("random", "libero_spatial", s, 50, RANDOM_STALE_SHAS) for s in range(4)]
)

# random×libero_spatial seed 4 already ran at the fix commit and must be
# carried through untouched (run_sweep's resume skips it as complete).
KEEP_CELL = TargetCell("random", "libero_spatial", 4, 50, frozenset())

# Rows outside the 9 target cells + the keep cell. Invariant across every
# stage of the operation.
EXPECTED_OTHER_ROWS = EXPECTED_TOTAL_ROWS - sum(c.n_episodes for c in TARGET_CELLS) - 50

# Printed by prepare; fired by the orchestrator once the GPU frees.
LAUNCH_COMMAND = f"""\
cd {_REPO_ROOT} \\
  && python scripts/rerun_post51_cells.py prepare \\
  && {{ [ -n "${{DISPLAY:-}}" ] || {{ [ -S /tmp/.X11-unix/X0 ] && export DISPLAY=:0; }}; }} \\
  && scripts/with_gpu_lock.sh --timeout 0 -- scripts/run_capped.sh 16G -- \\
       python scripts/run_sweep.py --config {RERUN_CONFIG} --resume \\
       >> logs/rerun-post51.log 2>&1 \\
  && python scripts/rerun_post51_cells.py finalize"""


# --------------------------------------------------------------------- #
# Ancestry check (injection point for tests)                            #
# --------------------------------------------------------------------- #


def _git_is_post_fix(code_sha: str) -> bool:
    """True iff the #51 fix commit is an ancestor of ``code_sha``."""
    result = subprocess.run(
        ["git", "-C", str(_REPO_ROOT), "merge-base", "--is-ancestor", FIX_SHA, code_sha],
        capture_output=True,
        timeout=10,
        check=False,
    )
    if result.returncode not in {0, 1}:
        raise RuntimeError(
            f"git merge-base failed for {code_sha}: {result.stderr.decode(errors='replace')}"
        )
    return result.returncode == 0


# Tests monkeypatch this (same pattern as run_sweep._run_subprocess) so
# finalize is exercisable on synthetic shas without a git repo.
_is_post_fix: Callable[[str], bool] = _git_is_post_fix


# --------------------------------------------------------------------- #
# Row selection                                                         #
# --------------------------------------------------------------------- #


def _cell_mask(df: pd.DataFrame, cell: TargetCell) -> pd.Series:
    return (df["policy"] == cell.policy) & (df["env"] == cell.env) & (df["seed"] == cell.seed)


@dataclass(frozen=True)
class CellPlan:
    """Prepare-time classification of one target cell."""

    cell: TargetCell
    n_rows: int
    sha_counts: dict[str, int]
    action: str  # "delete" | "already_replaced" | "awaiting_rerun"


def classify_target_cells(df: pd.DataFrame) -> list[CellPlan]:
    """Classify each target cell as delete / already_replaced / awaiting_rerun.

    * ``delete``: exactly ``n_episodes`` rows, ALL at stale code_shas —
      the untouched original cell.
    * ``already_replaced``: ``n_episodes`` rows, none stale — a completed
      re-run (prepare re-runs are no-ops on these).
    * ``awaiting_rerun``: zero rows (deleted, not yet re-filled) or a
      fresh partial that ``plan_resume`` will drop + re-queue itself.

    Anything else (stale/fresh mix in one cell, wrong full-cell count)
    violates cell atomicity and raises — operator inspects by hand.
    """
    plans: list[CellPlan] = []
    for cell in TARGET_CELLS:
        rows = df[_cell_mask(df, cell)]
        sha_counts = rows["code_sha"].value_counts().to_dict()
        stale = rows["code_sha"].isin(cell.stale_shas)
        n_stale = int(stale.sum())

        if n_stale and n_stale != len(rows):
            raise ValueError(
                f"{cell.display}: {n_stale}/{len(rows)} rows stale — stale/fresh mix "
                f"violates cell atomicity ({sha_counts}); refusing to touch it"
            )
        if n_stale:
            if len(rows) != cell.n_episodes:
                raise ValueError(
                    f"{cell.display}: {len(rows)} stale rows, expected {cell.n_episodes} "
                    f"({sha_counts}); refusing to delete an unexpected shape"
                )
            action = "delete"
        elif len(rows) == cell.n_episodes:
            action = "already_replaced"
        else:
            action = "awaiting_rerun"
        plans.append(CellPlan(cell=cell, n_rows=len(rows), sha_counts=sha_counts, action=action))
    return plans


def _check_invariants(df: pd.DataFrame) -> None:
    """Guards that hold at EVERY stage: keep-cell untouched, other rows intact."""
    keep_rows = df[_cell_mask(df, KEEP_CELL)]
    keep_shas = set(keep_rows["code_sha"].unique())
    if len(keep_rows) != KEEP_CELL.n_episodes or keep_shas != {FIX_SHA}:
        raise ValueError(
            f"keep cell {KEEP_CELL.display} unexpected: {len(keep_rows)} rows at "
            f"{sorted(keep_shas)}; expected {KEEP_CELL.n_episodes} rows at {FIX_SHA[:8]}"
        )

    target_mask = _cell_mask(df, KEEP_CELL)
    for cell in TARGET_CELLS:
        target_mask |= _cell_mask(df, cell)
    n_other = int((~target_mask).sum())
    if n_other != EXPECTED_OTHER_ROWS:
        raise ValueError(
            f"rows outside the target cells changed: {n_other} != {EXPECTED_OTHER_ROWS}"
        )


# --------------------------------------------------------------------- #
# prepare                                                               #
# --------------------------------------------------------------------- #


def _timestamp() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y%m%d-%H%M%S")


def prepare(sweep_dir: Path, *, dry_run: bool) -> int:
    parquet = sweep_dir / CANONICAL_NAME
    manifest = sweep_dir / MANIFEST_NAME
    if not parquet.exists():
        logger.error("canonical parquet not found: %s", parquet)
        return 3

    df = load_results(parquet)
    _check_invariants(df)
    plans = classify_target_cells(df)

    for plan in plans:
        logger.info(
            "%-32s %-16s rows=%-3d %s",
            plan.cell.display,
            plan.action,
            plan.n_rows,
            {k[:8]: v for k, v in plan.sha_counts.items()},
        )

    to_delete = [p for p in plans if p.action == "delete"]
    n_delete = sum(p.n_rows for p in to_delete)

    if not to_delete:
        logger.info("no stale rows left to delete (idempotent no-op); launch/resume with:")
        print(LAUNCH_COMMAND)
        return 0

    if dry_run:
        logger.info(
            "--dry-run: would back up %s + %s and delete %d row(s) from %d cell(s)",
            parquet.name,
            manifest.name,
            n_delete,
            len(to_delete),
        )
        print(LAUNCH_COMMAND)
        return 0

    ts = _timestamp()
    parquet_bak = sweep_dir / f"results.{_BACKUP_STEM}-{ts}.bak.parquet"
    shutil.copy2(parquet, parquet_bak)
    logger.info("backup: %s (%d rows)", parquet_bak, len(df))
    if manifest.exists():
        manifest_bak = sweep_dir / f"sweep_manifest.{_BACKUP_STEM}-{ts}.bak.json"
        shutil.copy2(manifest, manifest_bak)
        logger.info("backup: %s", manifest_bak)
    else:
        logger.warning("no %s to back up (finalize will skip the restore)", MANIFEST_NAME)

    delete_mask = pd.Series(False, index=df.index)
    for plan in to_delete:
        cell_stale = _cell_mask(df, plan.cell) & df["code_sha"].isin(plan.cell.stale_shas)
        delete_mask |= cell_stale
    kept = df[~delete_mask].reset_index(drop=True)
    if len(kept) != len(df) - n_delete:
        raise ValueError(f"delete mask removed {len(df) - len(kept)} rows, expected {n_delete}")
    _atomic_write_parquet(parquet, kept)

    # Re-read + re-verify: the on-disk parquet must load clean, with the
    # invariants intact and zero delete-class rows remaining.
    df_after = load_results(parquet)
    _check_invariants(df_after)
    remaining = [p for p in classify_target_cells(df_after) if p.action == "delete"]
    if len(df_after) != len(df) - n_delete or remaining:
        raise ValueError(
            f"post-delete verification failed: rows {len(df)}->{len(df_after)} "
            f"(expected -{n_delete}), {len(remaining)} delete-class cell(s) remain"
        )

    logger.info(
        "deleted %d stale row(s) from %d cell(s); parquet now %d rows; rollback: cp %s %s",
        n_delete,
        len(to_delete),
        len(df_after),
        parquet_bak,
        parquet,
    )
    logger.info("launch the re-run with:")
    print(LAUNCH_COMMAND)
    return 0


# --------------------------------------------------------------------- #
# finalize                                                              #
# --------------------------------------------------------------------- #


def _pretrained_policies(df: pd.DataFrame) -> set[str]:
    """Parquet policies that are not registry baselines.

    A policy absent from the registry is treated as pretrained
    (conservative: it gets the ancestry check, not a pass).
    """
    registry = PolicyRegistry.from_yaml(POLICIES_YAML)
    out: set[str] = set()
    for name in df["policy"].unique():
        try:
            if registry.get(str(name)).is_baseline:
                continue
        except KeyError:
            pass
        out.add(str(name))
    return out


def finalize(sweep_dir: Path) -> int:
    parquet = sweep_dir / CANONICAL_NAME
    if not parquet.exists():
        logger.error("canonical parquet not found: %s", parquet)
        return 3

    df = load_results(parquet)
    errors: list[str] = []

    if len(df) != EXPECTED_TOTAL_ROWS:
        errors.append(f"total rows {len(df)} != {EXPECTED_TOTAL_ROWS}")

    try:
        _check_invariants(df)
    except ValueError as exc:
        errors.append(str(exc))

    for cell in TARGET_CELLS:
        rows = df[_cell_mask(df, cell)]
        shas = sorted(set(rows["code_sha"].unique()))
        if len(rows) != cell.n_episodes:
            errors.append(f"{cell.display}: {len(rows)} rows != {cell.n_episodes}")
            continue
        if len(shas) != 1:
            errors.append(f"{cell.display}: mixed code_sha {shas}")
            continue
        if not _is_post_fix(shas[0]):
            errors.append(f"{cell.display}: code_sha {shas[0][:8]} is PRE-#51")

    # The point of the whole exercise: every pretrained row is post-#51.
    pretrained = _pretrained_policies(df)
    pre_rows = df[df["policy"].isin(pretrained)]
    for sha, n in pre_rows["code_sha"].value_counts().items():
        if not _is_post_fix(str(sha)):
            pols = sorted(pre_rows.loc[pre_rows["code_sha"] == sha, "policy"].unique())
            errors.append(f"pretrained rows still PRE-#51: {n} row(s) at {str(sha)[:8]} ({pols})")

    if errors:
        for err in errors:
            logger.error("FAIL: %s", err)
        logger.error(
            "finalize FAILED (%d check(s)); parquet left as-is. Resume the re-run or "
            "roll back from results.%s-*.bak.parquet",
            len(errors),
            _BACKUP_STEM,
        )
        return 1

    _restore_manifest(sweep_dir)
    logger.info(
        "finalize PASSED: %d rows, %d target cell(s) post-#51, pretrained policies %s "
        "all post-#51 eval.py",
        len(df),
        len(TARGET_CELLS),
        sorted(pretrained),
    )
    return 0


def _restore_manifest(sweep_dir: Path) -> None:
    """Archive run_sweep's re-run manifest and restore the original.

    ``run_sweep`` unconditionally writes ``sweep_manifest.json`` next to
    its ``results_path``, clobbering the canonical full-sweep manifest
    that ``make publish`` ships. The re-run's manifest is preserved under
    ``sweep_manifest.rerun_post51-<TS>.json`` for provenance.
    """
    manifest = sweep_dir / MANIFEST_NAME
    backups = sorted(sweep_dir.glob(f"sweep_manifest.{_BACKUP_STEM}-*.bak.json"))
    if not backups:
        logger.warning("no manifest backup found; leaving %s as-is", manifest)
        return
    backup = backups[-1]
    if manifest.exists() and manifest.read_bytes() == backup.read_bytes():
        logger.info("manifest already matches backup %s (no-op)", backup.name)
        return
    if manifest.exists():
        archive = sweep_dir / f"sweep_manifest.rerun_post51-{_timestamp()}.json"
        shutil.copy2(manifest, archive)
        logger.info("archived re-run manifest -> %s", archive)
    shutil.copy2(backup, manifest)
    logger.info("restored original manifest from %s", backup.name)


# --------------------------------------------------------------------- #
# CLI                                                                   #
# --------------------------------------------------------------------- #


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Replace the last pre-#51 pretrained rows in the canonical sweep "
            "parquet: backup + delete (prepare), re-run via run_sweep, then "
            "verify + restore the manifest (finalize)."
        ),
    )
    parser.add_argument(
        "stage",
        choices=["prepare", "finalize"],
        help="prepare: backup + delete stale rows; finalize: verify + restore manifest.",
    )
    parser.add_argument(
        "--sweep-dir",
        type=Path,
        default=DEFAULT_SWEEP_DIR,
        help="Sweep directory (default results/sweep-full; point at a copy to rehearse).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="prepare only: report the per-cell plan without writing anything.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    args = _build_parser().parse_args(argv)
    try:
        if args.stage == "prepare":
            return prepare(args.sweep_dir, dry_run=args.dry_run)
        return finalize(args.sweep_dir)
    except ValueError as exc:
        logger.error("%s aborted: %s", args.stage, exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
