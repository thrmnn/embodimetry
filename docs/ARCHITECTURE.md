# Architecture

> Source of truth: [`docs/DESIGN.md`](DESIGN.md) (technical design).
> This file is the short index — links and diagrams only.

## High-level dataflow

```
                 ┌────────────────────────┐
                 │  configs/sweep_*.yaml  │
                 └────────────┬───────────┘
                              │
              ┌───────────────▼───────────────┐
              │  scripts/run_sweep.py         │
              │  (orchestrator + checkpoint)  │
              └─┬──────────┬───────────────┬──┘
                │          │               │
                ▼          ▼               ▼
       ┌──────────┐  ┌──────────┐   ┌─────────────┐
       │ envs.py  │  │policies  │   │  eval.py    │
       │ registry │  │ registry │   │ (runs cell) │
       └──────────┘  └──────────┘   └──────┬──────┘
                                           │
                              ┌────────────┴────────────┐
                              ▼                         ▼
                      ┌───────────────┐         ┌──────────────┐
                      │ render.py     │         │ stats.py     │
                      │ MP4 + thumbs  │         │ bootstrap CI │
                      └───────┬───────┘         └──────┬───────┘
                              │                        │
                              └───────────┬────────────┘
                                          ▼
                              ┌──────────────────────┐
                              │ results/<sweep>/     │
                              │   ├ results.parquet  │
                              │   ├ videos/*.mp4     │
                              │   └ manifest.json    │
                              └──────────┬───────────┘
                                         │
                          ┌──────────────┴───────────────┐
                          ▼                              ▼
                  ┌──────────────────┐          ┌────────────────────┐
                  │ HF Hub dataset   │          │ space/app.py       │
                  │ thrmnn/          │ <─reads─ │ Gradio UI          │
                  │ embodimetry-v1 │          │ (leaderboard +     │
                  │                  │          │  browse-rollouts)  │
                  └──────────────────┘          └────────────────────┘
```

## Module layout

| Module | Purpose |
| --- | --- |
| `embodimetry.envs` | Sim env registry: gym IDs, `max_steps`, success thresholds |
| `embodimetry.policies` | Policy registry: HF Hub repo IDs + revision SHAs + env compat |
| `embodimetry.eval` | Core eval loop: `(policy, env, seed, n_episodes) -> CellResult` |
| `embodimetry.stats` | Bootstrap CIs, paired Wilcoxon, Cohen's h, effect sizes |
| `embodimetry.render` | Episode → MP4 (256px / 10fps / ≤2MB), thumbnail strips |
| `embodimetry.checkpointing` | Per-cell skip logic on resume |
| `embodimetry.cli` | `embodimetry` entrypoint |

## Data contracts

See `docs/DESIGN.md` § Architecture sketch for the full `results.parquet`
schema and `manifest.json` field list. Headlines:

- **Granularity**: one row per episode (5 seeds × ≤50 episodes per cell).
- **Join key**: `timestamp_utc` joins parquet rows to `manifest.json`.
- **Reproducibility key**: `(policy, env, seed, episode_index)`.

## Reproducibility & seeding contract

Mid-cell resume is **not** bit-reproducible because the torch generator advances
across episodes within a cell. `checkpointing.py` only resumes at cell boundaries.
Full seeding contract in `docs/DESIGN.md` § Methodology.

## Deploy

- **GitHub repo**: `thrmnn/embodimetry` — code, this repo.
- **HF Hub dataset**: `thrmnn/embodimetry-v1` — parquet + videos.
- **HF Space**: `huggingface.co/spaces/thrmnn/embodimetry` — its own git remote.
  `space/` ships via `make space-deploy` which runs `git push hf-space main`.

No GitHub Actions deploy workflow in v1 — the bench itself runs on the dev box,
not in CI. CI is for lint + typecheck + fast tests only.
