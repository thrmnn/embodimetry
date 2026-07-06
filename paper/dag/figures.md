---
status: review
depends_on: [results]
---

# Figures — embodimetry

> One entry per figure that supports a MAIN or SPINE-SUPPORTING result in
> `results.md`. A figure with no result behind it doesn't belong here.
> Figure-adjacent decisions that aren't themselves a figure (cut calls,
> clarification notes) live in the prose below the table, not as rows in it.
>
> **Passed a council review + two bulletproofing rounds** (2026-07-06). Three
> real bugs found and fixed during this pass — see the resolved items below.

| Figure | Source | Supports | Caption draft | Status |
|---|---|---|---|---|
| `forest_plot` | `src/embodimetry/figures.py::forest_plot` | L0 cross-paradigm contract (MAIN) | "Per-cell success rate with Wilson 95% CI, all paradigms on one contract." | **Fixed this pass** — the rendered title hardcoded "N=250/cell," but `diffusion_policy×pusht` is genuinely N=125 (auto-downscoped) and *is* plotted, not filtered. Title no longer makes the uniform-N claim; `main.tex`'s own caption already correctly said "pools the cell's 5×n_ep episodes." Regenerated and re-embedded. |
| `act_norm_ablation` | `src/embodimetry/figures.py` (2×2 ablation) | Self-caught normalization bug (MAIN) | "2×2 ablation: recovery is 100% the normalization fix, 0% temporal ensembling." | **Fixed this pass** — the "fixed" row's Hub-vs-paper-settings comparison (0.812 vs 0.768) was asserted as "overlapping CIs" with no effect size, despite `main.tex`'s own methodology mandating Cohen's h for exactly this kind of claim (and reporting it for two other overlap claims in the same paper). Added: $h{=}0.108$ (small), computed via `embodimetry.stats.cohens_h`, now in `main.tex` Table `tab:act-ablation` caption. |
| `replication_scatter` | `src/embodimetry/figures.py::replication_scatter` | L0 contract / cross-check vs. reported paper rates | Traffic-light scatter, paper rate vs. our replication | **Fixed this pass — was genuinely stale.** The per-task LIBERO pooling fix (#205, commit `7b5f654`, 2026-06-14) never touched the committed figure files; the embedded PDF was last regenerated in commit `5452fc8` (2026-06-05), 9 days *before* the fix. The paper was shipping the pre-#205 single-task comparison. Regenerated from current `src/embodimetry/figures.py` + `results/sweep-full/results.parquet`; `tests/test_figures.py` (20 tests) passes against the new output. |
| `failure_taxonomy` | `docs/assets/make_failure_taxonomy_fig.py` | Failure taxonomy (SPINE-SUPPORTING, `results.md`) | "Curated, non-random labeled sample; six-mode taxonomy" | **Pending — PR #187 not yet merged** (auto-merge armed, waiting on CI). Now has a matching `results.md` row (was missing one, a cross-artifact consistency bug caught during the adversarial review pass). Don't treat as available until #187 lands. |

## Cut

**`act_probe_bar`** — not merely redundant with `act_norm_ablation`, actively
contradicted by it. Its "probe" arm (0.764) changes *two* variables at once
(normalization fix + paper inference settings), so it can't isolate either
one; its own title text says "inference settings are the load-bearing
variable," which the correctly-isolated 2×2 ablation shows is false
(normalization is 100% of the recovery). The 4 rendered output files
(`paper/figures/{paper,deck,web}/act_probe_bar.*`) have been deleted — the
underlying `act_probe_bar()` function and its tests in
`src/embodimetry/figures.py`/`tests/test_figures.py` are untouched (it's a
legitimate library function, just not part of this submission's figure set).

## Notes (not figures)

- **0.824 vs 0.812 — not a bug.** `main.tex`'s ablation-table caption already
  explains the fixed-Hub-default cell (0.812) is "the same condition as the
  canonical leaderboard number 0.824... measured in a separate N=250 run;
  the two agree within CI." Noted here so a reader of this file alone
  doesn't flag it as an unexplained inconsistency.
- **L3 nav-vs-contact — closed, table stands.** A two-endpoint, N=6-per-cell
  contrast is 4 numbers total; a dedicated figure would be decorative, not
  informative, at that data density. `main.tex` Table `tab:l3` is
  sufficient; no figure needed.

## Remaining open item

`replication_scatter`'s regenerated output has not been visually re-inspected
(only re-rendered + test-suite-verified) — worth a quick look before this
locks, since the point of the #205 fix was a specific visual claim (per-task
LIBERO pooling shown correctly) that automated tests don't fully assert.

## Process fix (from the final adversarial pass)

The stale-`replication_scatter` bug this pass found and fixed is itself an
instance of the exact silent-drift problem the paper's self-audit story is
about — a code fix (#205) landed without its dependent committed artifact
being regenerated, and nothing caught it for weeks. A CI-enforced guard was
attempted (byte-diffing regenerated SVGs against the committed ones) and
abandoned: matplotlib embeds non-deterministic clip-path IDs per render, so
exact-match diffing is inherently flaky, not just a strip-the-timestamp
problem. Landed instead: `make paper-figures` (regenerates all three
canonical figures from current code + `results/sweep-full/results.parquet`
in one command, `Makefile`) — this doesn't auto-detect drift, but it makes
"did you forget to regenerate" a one-command question rather than a
multi-step manual one. Run it before any paper submission or whenever
`src/embodimetry/figures.py` changes.
