---
status: review
depends_on: [proposal]
---

# Results synthesis — embodimetry

> Extracted from `paper/main.tex` §Results/§L3 and `docs/SHIP_READINESS.md`.
>
> **Passed a council review + one bulletproofing round** (2026-07-06). The
> original MAIN/OPTIONAL binary was wrong — fixed to three tiers below, see
> the note.

**Council finding, fixed:** the original draft of this file mislabeled L1
and L2 as "OPTIONAL — appendix or cut," but `main.tex` line 475 states
outright that "Table~\ref{tab:ladder} is the spine of the paper" — and that
table contains L0, both L1 rows, L2, *and* L3 together, in the main body.
The paper never cuts L1/L2; it keeps them prominently as the "undramatic"
findings that make the contract's honesty legible. MAIN vs OPTIONAL was the
wrong axis; a finding can be in the paper's spine without being one of the
abstract's three headline contributions. Three tiers now:

## MAIN — one of the paper's three headline contributions

| Finding | Pointer | Ties to |
|---|---|---|
| Self-caught ACT×aloha normalization bug: $\hat p{=}0.016 \to 0.824$, isolated 100% to the norm fix via a 2×2 ablation (not temporal ensembling; Cohen's $h{=}0.108$ for the fixed-Hub-vs-fixed-paper comparison, added to `main.tex` Table `tab:act-ablation` during this pass) | `results/sweep-full/`, `paper/figures/paper/act_norm_ablation.{pdf,svg}` | RQ2 |
| L0 cross-paradigm contract itself: DP×pusht 0.816 [0.739,0.874], ACT×aloha 0.824 [0.772,0.866], SmolVLA×LIBERO 0.252–0.928 across 4 suites, all on one Wilson/bootstrap/MDE spine | `results/sweep-full/results.parquet`, `paper/figures/paper/forest_plot.{pdf,svg}` (regenerated this pass — title no longer overclaims a uniform N=250/cell; the auto-downscoped `diffusion_policy×pusht` cell is genuinely N=125) | RQ1 |
| L3 two-endpoint nav-vs-contact replication: Wall (nav) JEPA-WM 4/6 ≈ DINO-WM 3/6; PushT (contact) JEPA-WM 0/6 ≈ DINO-WM 0/6 — replicates across two independent WM families under matched receding-horizon MPC. **Caveats, kept inline per `main.tex`'s own repeated framing and `tests/test_no_ungated_l3_claims.py`'s guard:** this is a *two-endpoint contrast*, $N{=}6$ per cell, one environment per endpoint — not a cross-env law, not a measured curve; the gradient middle is unmeasured. | cross-repo `lerobot-wm-research`, `docs/blog/capability-ladder-audit.md` | RQ3 |

## SPINE-SUPPORTING — in the paper's main ladder table, not a headline

| Finding | Why not MAIN (not "why cut") | Ties to |
|---|---|---|
| L1 ACT continued fine-tune: 0.824 → 0.864, CIs overlap, Cohen's $h{=}0.11$ below N=250 MDE | Genuinely undramatic/null — it earns its place in the spine table precisely *because* it's honest about being within noise, not because it's a weak result to hide | RQ4 |
| L1 SmolVLA LoRA collapse: 0.252 → ~0 on libero_10 | Bug-driven negative (small demo budget vs. large adapter + reward structure); real evidence the contract catches failures, secondary to the norm-bug story only in that it isn't one of the abstract's three headlines | RQ2 (secondary), RQ4 |
| L2 classical PushT controller: 0.012 [0.004, 0.035] strict-bar clear rate despite ~0.50 mean coverage | The "learning buys the last fraction of precision" reading — in the spine table, quantitative, just not headline-grade on its own | RQ4 |
| Floor-baseline sanity check: no-op 0/1500 across all envs; random clears the floor only on `aloha_transfer_cube` at 0.052 | Direct evidence for the abstract's "honest negatives kept on the board" claim — was missing from this synthesis entirely; added during bulletproofing | RQ1 |
| Pooled SmolVLA×LIBERO rate: 0.621 [0.591, 0.651] (`main.tex` line ~765) | Supporting number for the L0 contract row above, not separately headline | RQ1 |
| Methodology caveats (v1.0.1 audit): task-scope mismatch, LIBERO step-cap check, XVLA deferral | Cited, numbered caveats in the draft — not optional color, but not a finding in its own right | RQ1 (integrity) |
| Failure taxonomy figure (N=6 labeled rollouts) — **pending**, backs PR #187 which is not yet merged | Descriptive detail supporting the self-audit's credibility, not a headline claim itself; do not treat as available until #187 lands | RQ2 (secondary) |

## APPENDIX-OR-CUT — genuinely not ready or not paper-body material

| Finding | Why | Ties to |
|---|---|---|
| v1.1 LIBERO-10 per-task pooled results | Sweep still in progress (~1/3 done per `docs/SHIP_READINESS.md` M1) — not citable yet | RQ1 (extension) |

## Open gap — blocks `draft` locking

The **only remaining `\todo{}` in `paper/main.tex`** (line ~541) is the
SmolVLA-LoRA post-collapse $\hat p$/$N$, in the SPINE-SUPPORTING row above.
`main.tex`'s own comment says this number is *"not committed to this
tree"* — meaning it likely exists only outside this repo (Théo's local
notes/scratch), not that it's simply unfound. **Action needed from Théo:**
locate the real fine-tune-track summary, or confirm it doesn't exist, in
which case cut the row with a one-line note rather than leaving the `\todo`.

## Note on terminology (flagged, not changed here)

`main.tex` line 533 and this file both call 0.123 "the N=250 MDE." Per
`docs/MDE_TABLE.md` §TL;DR, 0.123 is actually the **closed-form Wilson
inconclusive-band half-width** (a loose independence bound); the doc's own
**empirical, bootstrap-calibrated MDE at p=0.5, N=250 is 0.15** — a
distinct, more conservative quantity that `MDE_TABLE.md` deliberately keeps
separate. This doesn't change any conclusion here (Δ=0.040 is below both
values, so "within noise" holds either way, more strongly under 0.15) — kept
as inherited terminology from `main.tex` rather than silently diverging from
the source it summarizes. Worth fixing in `main.tex` itself on a future
revision, not something this synthesis file should unilaterally contradict.
