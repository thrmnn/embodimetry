---
status: draft
depends_on: [proposal]
---

# Results synthesis — embodimetry

> Extracted from `paper/main.tex` §Results/§L3 and `docs/SHIP_READINESS.md`.
> The MAIN/OPTIONAL split below matches what the existing draft already does
> editorially (L1/L2 framed as secondary, off the public leaderboard per
> README) — this file makes that split explicit and reviewable rather than
> implicit in prose, per the DAG methodology.

## MAIN — goes in the paper body

| Finding | Pointer | Ties to |
|---|---|---|
| Self-caught ACT×aloha normalization bug: $\hat p{=}0.016 \to 0.824$, isolated 100% to the norm fix via a 2×2 ablation (not temporal ensembling) | `results/sweep-full/`, `paper/figures/paper/act_norm_ablation.{pdf,svg}` | RQ2 |
| L0 cross-paradigm contract itself: DP×pusht 0.816 [0.739,0.874], ACT×aloha 0.824 [0.772,0.866], SmolVLA×LIBERO 0.252–0.928 across 4 suites, all on one Wilson/bootstrap/MDE spine | `results/sweep-full/results.parquet`, `paper/figures/paper/forest_plot.{pdf,svg}` | RQ1 |
| L3 two-endpoint nav-vs-contact replication: Wall (nav) JEPA-WM 4/6 ≈ DINO-WM 3/6; PushT (contact) JEPA-WM 0/6 ≈ DINO-WM 0/6 — replicates across two independent WM families under matched receding-horizon MPC | cross-repo `lerobot-wm-research`, `docs/blog/capability-ladder-audit.md` | RQ3 |

## OPTIONAL — appendix or cut

| Finding | Why optional | Ties to |
|---|---|---|
| L1 ACT continued fine-tune: 0.824 → 0.864, CIs overlap, Cohen's $h{=}0.11$ below N=250 MDE | Explicitly a within-noise null result — valuable as honesty evidence, not a headline | RQ4 |
| L1 SmolVLA LoRA collapse: 0.252 → ~0 on libero_10 | Bug-driven negative (small demo budget vs. large adapter + reward structure); supports RQ2's "the contract catches failures" but secondary to the norm-bug story | RQ2 (secondary) |
| L2 classical PushT controller: 0.012 [0.004, 0.035] strict-bar clear rate despite ~0.50 mean coverage | Single secondary env; supports RQ1/RQ4 but not headline-grade on its own | RQ4 |
| v1.1 LIBERO-10 per-task pooled results | Sweep still in progress (~1/3 done per `docs/SHIP_READINESS.md` M1) — not citable yet | RQ1 (extension) |

## Open gap — blocks `draft` locking

The **only remaining `\todo{}` in `paper/main.tex`** (line ~541) is exactly
the OPTIONAL L1 SmolVLA-LoRA row above: *"confirm exact post-LoRA $\hat p$
and $N$ from the fine-tune track summary; not committed to this tree."* Since
that finding is OPTIONAL rather than MAIN, it doesn't block `results.md` or
`figures.md`, but it does block `draft` reaching a submittable state — needs
the real fine-tune-track summary pulled in, or the row explicitly cut with a
one-line note on why.
