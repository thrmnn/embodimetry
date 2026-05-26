# scripts/

Operator-facing entry points for the bench. The library code lives under
`src/lerobot_bench/`; everything here is a thin CLI wrapper around it.

## Figure generation

| Script | What it does |
|---|---|
| `replication_scatter.py` | Renders the paper-vs-measured replication scatter (Wilson 95% CI per cell, traffic-light coloring) to `docs/assets/fig-replication-scatter.{svg,png}`. Reads `results/sweep-full/results.parquet` + paper rates from `configs/policies.yaml`. Pass `--show-deferred` to grey-include XVLA. |

## Sweep + evaluation

| Script | What it does |
|---|---|
| `run_one.py` | Run a single (policy, env, seed) cell; emits a row to `results.parquet`. |
| `run_sweep.py` | Drive the full matrix from `configs/sweep_full.yaml` or `sweep_mini.yaml`. |
| `reproduce_cell.py` | Bit-for-bit reproduce a previously-recorded cell from its sweep manifest entry. |
| `calibrate.py` / `calibrate_mde.py` | Per-cell wall-time + MDE calibration, prior to running a sweep. |
| `merge_calibration.py` | Fold calibration outputs into a single calibration parquet. |
| `auto_downscope.py` | Trim a sweep to fit a wall-clock budget based on calibration. |

## Publishing + review

| Script | What it does |
|---|---|
| `publish_results.py` | Push a sweep's parquet + MP4 corpus + manifest to the public HF dataset. |
| `review_results.py` | Local Gradio reviewer over a results parquet. |
| `prefetch_vlas.py` | Pre-download VLA weights so a sweep run doesn't first-touch the Hub. |

## Watchdog + safety

| Script | What it does |
|---|---|
| `watchdog.py` | RAM watchdog for VLA cells; kills the run on breach. |
| `run_capped.sh` | Wrap a child process under cgroup `MemoryMax`. |
| `run_with_caps.sh` | Run a sweep with combined RAM + GPU caps. |
| `with_gpu_lock.sh` | Acquire a flock-based GPU lease before invoking the child. |
| `sweep_throttle.sh` | Sleep/yield between cells to keep host load under a ceiling. |

## Conventions

- Every script is invokable as `python scripts/<name>.py --help`.
- Default paths assume you ran from the repo root (e.g. `results/sweep-full/results.parquet`).
- No script writes outside `results/`, `docs/assets/`, or `outputs/` unless the
  flag explicitly says so.
