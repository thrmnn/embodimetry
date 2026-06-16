# Development

The dev/contributor front door for **embodimetry**. This is a hub: it owns the
developer journey end-to-end and links out to the detailed docs rather than
duplicating them. If you only want to *read* the leaderboard, start at the
[README](../README.md) and the [live dashboard](https://huggingface.co/spaces/thrmnn/embodimetry)
instead — none of this is needed for that.

> The operator/internal docs linked below (RUNBOOK, MONITORING, ORCHESTRATION,
> PUBLISH_RUNBOOK) are **dev-facing**, not part of the end-user surface.

---

## Local dev setup

**Requirements**

- Python **3.12**.
- A CUDA-capable GPU for sim runs. The leaderboard *reader* (`examples/read_results.py`)
  runs CPU-only; everything that produces a rollout needs a GPU.
- Pinned **`lerobot==0.5.1`** (recorded in `pyproject.toml`; every published row
  is anchored to it).

**Reference hardware.** The v1 sweep ran on an NVIDIA **RTX 4060 Laptop (8 GB
VRAM)**, 32 GB host RAM, Ubuntu on **WSL2**. The 8 GB VRAM ceiling is why the
sweep auto-downscopes slow/heavy cells (see [auto-downscope](#auto-downscope-and-the-vram-budget))
and why heavy workloads run under a kernel-enforced **18 GB cgroup memory cap**
(`scripts/run_capped.sh`). On larger hardware these guards simply never trigger.

**Install (conda, editable, all extras)**

```bash
git clone https://github.com/thrmnn/embodimetry.git && cd embodimetry
conda activate lerobot          # Python 3.12 env with lerobot 0.5.1
pip install -e ".[all]"         # sim + viz + space + dev extras
pre-commit install
```

`make dev-setup` does the `install[all]` + pre-commit-hooks step in one shot.

---

## Make targets

| Target | What it does |
|---|---|
| `make install` | Editable install with all extras (sim + viz + space + dev) |
| `make install-dev` | Editable install, dev extras only |
| `make dev-setup` | `install[all]` + pre-commit hooks (one-shot contributor setup) |
| `make lint` | `ruff check` |
| `make format` | `ruff format` |
| `make typecheck` | `mypy` |
| `make test` | Full pytest suite |
| `make test-fast` | Skip `slow` / `gpu` / `sim` marks |
| `make all` | lint + typecheck + test |
| `make dashboard` | Launch the local operator dashboard (Gradio) → http://127.0.0.1:7860 |
| `make calibrate` | Per-policy step-latency + VRAM probe (feeds auto-downscope) |
| `make run-one ARGS="--policy ... --env ... --seed N"` | Single-cell debug run |
| `make reproduce CELL=policy/env/seed` | Verify one published cell |
| `make sweep ARGS="--config ..."` | Generic sweep dispatch |
| `make sweep-mini` | Smoke sweep (2 baselines × 2 envs × 2 seeds × 25 ep) |
| `make sweep-full` | Full benchmark sweep (overnight; **no** cgroup cap) |
| `make publish SWEEP=results/sweep-full` | Push a sweep's artifacts to the HF Hub dataset (`DRY_RUN=1` to stage offline) |

**Render figures.** The paper/README figures regenerate deterministically with
`python scripts/render_figures.py`; the headline-cells mini-parquet that
`examples/read_results.py` reads is rebuilt with `python scripts/make_results_mini.py`.

Pre-commit hooks run ruff (lint + format) and mypy on every commit; the test
suite runs in CI on every push and PR.

---

## Running an eval

**One cell (debug).**

```bash
python scripts/run_one.py --policy act --env aloha_transfer_cube --seed 0 --n-episodes 5
```

This produces per-episode rows in `results/results.parquet` and rollout MP4s in
`results/videos/` — the same artifacts every leaderboard number is built from.
No GPU? `run_one.py` detects it and points you back at the zero-GPU reader
instead of crashing mid-rollout. First GPU run, expected output, and
common-issue fixes: **[`GETTING_STARTED.md`](GETTING_STARTED.md)**. Reproduce a
*published* cell exactly: **[`REPRODUCE.md`](REPRODUCE.md)**.

**The full sweep.**

```bash
# 1. Calibrate (~30 min — measures step latency + VRAM per cell)
make calibrate

# 2. Merge per-policy calibration JSONs (if you split the run)
python scripts/merge_calibration.py results/calibration-cheap.json \
    results/calibration-smolvla.json results/calibration-xvla.json \
    --out results/calibration-$(date +%Y-%m-%d).json

# 3. Generate sweep_full.yaml overrides from calibration
python scripts/auto_downscope.py results/calibration-$(date +%Y-%m-%d).json --apply

# 4. Launch under the 18 GB cgroup cap (overnight, ~8-15 hr)
scripts/launch_overnight_sweep.sh

# Watch progress
make dashboard   # → http://127.0.0.1:7860
```

Full operational procedure, watchdog, and recovery: **[`RUNBOOK.md`](RUNBOOK.md)**.
The v1.1 LIBERO sweep uses `configs/sweep_v11_libero.yaml` (10 tasks per suite).

### Auto-downscope and the VRAM budget

Calibration runs 20 steps per cell and flags `mean_step_ms > 100` (slow) or
`vram_peak_mb > 5500` (VRAM-pressured); `auto_downscope.py` then trims that
cell's episode budget so the full sweep fits the 8 GB / 18 GB envelope. Two v1
cells were downscoped to 25 ep/seed (N=125) this way. A pre-flight gate refuses
launch when baseline host RAM is already > 55% used, to protect other tenants.

---

## Operations (dev-facing)

| Doc | Owns |
|---|---|
| [`RUNBOOK.md`](RUNBOOK.md) | Running a sweep, watchdog, recovery, checkpoint-resume |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | GPU/VRAM/WSL2 failure modes and fixes |
| [`MONITORING.md`](MONITORING.md) | Dashboard, log tails, health signals during a run |
| [`ORCHESTRATION.md`](ORCHESTRATION.md) | Multi-agent worktree workflow, disjoint file ownership, merge drain |
| [`PUBLISH_RUNBOOK.md`](PUBLISH_RUNBOOK.md) | Pushing artifacts to the HF Hub dataset + deploying the Space |

---

## Architecture pointers

| Doc | Owns |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Module layout, data flow, registries, checkpointing |
| [`DESIGN.md`](DESIGN.md) | Methodology, seeding contract, statistics, eval contract |
| [`API.md`](API.md) | Public Python API (`run_cell_from_specs`, `wilson_ci`, …) |

Source lives in `src/embodimetry/` (eval, stats, render, registries,
checkpointing, figures). The eval pipeline is built to be extractable as
`lerobot.eval.multi_seed` for a follow-up upstream PR.

---

## Publishing and release

Releasing a dataset version is: finalize the sweep → render figures → publish to
the Hub → deploy the Space. The end-to-end procedure (Hub upload, version
tagging, Space subtree push, the gated checks that must pass first) is in
**[`PUBLISH_RUNBOOK.md`](PUBLISH_RUNBOOK.md)**. `make publish SWEEP=... DRY_RUN=1`
stages the upload offline first.

---

## Contributing

PRs and issues welcome — see [`../CONTRIBUTING.md`](../CONTRIBUTING.md) for the
branch/commit conventions and the multi-agent worktree workflow. Bringing a new
sim env into the matrix is a documented path:
[`ENV_CONTRIBUTION_GUIDE.md`](ENV_CONTRIBUTION_GUIDE.md).
