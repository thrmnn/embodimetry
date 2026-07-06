---
status: draft
depends_on: [results]
---

# Figures — embodimetry

> One entry per figure that supports a MAIN result in `results.md`. A figure
> with no MAIN result behind it doesn't belong here — cut it or promote/demote
> the result it supports first.

| Figure | Source | Supports (MAIN result) | Caption draft | Journal-readiness |
|---|---|---|---|---|
| `forest_plot` | `src/embodimetry/figures.py::forest_plot` | L0 cross-paradigm contract (all cells on one Wilson spine) | "Per-cell success rate with Wilson 95% CI, all paradigms on one contract." | Has paper/deck/web variants already; check colorblind-safe palette |
| `act_norm_ablation` | `src/embodimetry/figures.py` (2×2 ablation) | Self-caught normalization bug, 0.016→0.824 | "2×2 ablation: recovery is 100% the normalization fix, 0% temporal ensembling." | Paper variant exists; verify print-resolution PDF renders correctly at submission page width |
| `replication_scatter` | `src/embodimetry/figures.py::replication_scatter` | L0 contract / cross-check vs. reported paper rates | Traffic-light scatter, paper rate vs. our replication | Recently reworked to pool per-task LIBERO cells (#205, #7b5f654) — confirm this version, not the older per-suite one, is what's embedded |
| `act_probe_bar` | `src/embodimetry/figures.py` | Supporting detail for the norm-bug ablation (probe comparison) | — | Check whether this is MAIN-supporting or should fold into `act_norm_ablation`'s caption instead of standing alone |
| L3 nav-vs-contact figure | `docs/blog/capability-ladder-audit.md` (cross-repo `lerobot-wm-research`) | L3 two-endpoint replication | Wall vs. PushT, JEPA-WM vs. DINO-WM, receding-horizon MPC | **Not yet embedded in `paper/figures/`** — the L3 result is currently text/table only (Table `tab:l3`); decide whether a dedicated figure is worth the page budget or the table suffices |
| `failure_taxonomy` | `docs/assets/make_failure_taxonomy_fig.py` | Supporting detail, N=6 labeled rollouts | "Curated, non-random labeled sample; six-mode taxonomy" | **Pending — PR #187 not yet merged** (auto-merge armed, waiting on CI). Don't treat as available until it lands. |

## Open question

Two entries (`act_probe_bar`, and whether L3 needs its own figure vs. relying
on Table `tab:l3`) aren't cleanly tied to a single MAIN result yet — worth
Théo's call on whether to keep, fold, or cut before this locks.
