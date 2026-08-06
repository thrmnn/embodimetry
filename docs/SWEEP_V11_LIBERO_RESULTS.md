# v1.1 LIBERO 10-task sweep results

> **Status: ANALYZED + stats-rigor reviewed (2026-08-06).** The review's veto
> (episode-level Fisher test invalid under task clustering) and all must-fix
> findings are incorporated below — the primary test is task-as-sampling-unit.
> Sweep completed
> 2026-07-08: 200/200 cells, 0 failed, 0 errored episodes. Source:
> `results/sweep-v11-libero/results.parquet` (10,000 rows), config
> `configs/sweep_v11_libero.yaml`, manifest
> `results/sweep-v11-libero/sweep_manifest.json`. Total GPU wallclock ≈ 56.9 h.

## What this doc is

The empirical resolution of the **PR #84 scope mismatch** — the one v1.0.1
audit finding that had no runnable probe (`docs/PROBE_RESULTS_V1.0.1.md`
deferred it here). `docs/CLAIM_AUDIT_SMOLVLA.md` established that the SmolVLA
paper's LIBERO numbers (Shukor et al. 2025, §4.1, Table 2) are **per-suite
averages over all 10 tasks × 10 trials**, while v1 measured `task_id=0` only —
so v1's "−45.8 pp gap on libero_10" was an envelope claim, not an
apples-to-apples comparison. v1.1 runs **all 10 tasks of all 4 suites**
(smolvla_libero × 40 envs × 5 seeds × 50 episodes = 2,500 episodes per suite)
under the v1_legacy criterion, making the suite-averaged comparison identified
for the first time.

**Headline verdict: the gap survives suite-averaging in all four suites
(decisively for object/spatial/libero_10; marginally for goal — see §1).**

## 1. Suite-averaged rates vs. published

Pooled per suite via `stats.pool_binomial` (10 tasks × 250 episodes each; equal
episode weight = equal task weight here, matching the paper's equal-task
averaging). Because episodes cluster heavily by task (within-suite per-task
rates span 0.036–0.880; ANOVA ICC 0.10–0.26, design effect 25–65, effective
n ≈ 39–101 rather than 2,500), the **primary significance test treats the
task as the sampling unit**: a one-sample t of the 10 per-task rates against
the published suite mean, Holm–Bonferroni across the 4 suites
(`stats.holm_bonferroni`). Effect size `stats.cohens_h` on the pooled rates.

| Suite | Published (n=100) | v1.1 suite-avg (n=2500) | Gap | Cluster-robust 95% t-CI | Holm-adj p (task-level t) | Cohen's h |
|---|---|---|---|---|---|---|
| libero_spatial | 0.90 [0.826, 0.945] | **0.643** [0.624, 0.662] (1608/2500) | **−25.7 pp** | [0.466, 0.820] | 0.028 | 0.64 |
| libero_object | 0.96 [0.902, 0.984] | **0.684** [0.665, 0.702] (1709/2500) | **−27.6 pp** | [0.572, 0.795] | 0.0013 | 0.79 |
| libero_goal | 0.92 [0.850, 0.959] | **0.813** [0.797, 0.828] (2032/2500) | **−10.7 pp** | [0.724, 0.901] | 0.037 | 0.32 |
| libero_10 | 0.71 [0.615, 0.790] | **0.493** [0.473, 0.512] (1232/2500) | **−21.7 pp** | [0.322, 0.664] | 0.037 | 0.45 |

Brackets in the first two data columns are 95% Wilson CIs on each side's own
counts (descriptive; the Wilson interval on our side assumes iid episodes and
is too narrow under task clustering — the cluster-robust t-CI is the honest
uncertainty statement). All four suites reject at α=0.05 with the task as the
sampling unit, after Holm correction. A task-level Wilcoxon signed-rank
agrees (all p ≤ 0.027), and adding the published side's own n=100 binomial
SE (z-test on the difference of means) does not change any verdict
(p = 0.0022 / 1.7e-07 / 0.024 / 0.014). Episode-level Fisher exact tests give
far smaller p-values (2.1e-11 – 5.2e-03) but overstate the effective sample
size by the 25–65× design effect and are reported only as an anticonservative
bound, not as evidence. **Object and spatial reject decisively; goal and
libero_10 are solid but not overwhelming (adjusted p = 0.037 each)** — the
goal gap in particular (−10.7 pp, h=0.32, marginal p, and an unprobed
one-directional cap confound, see caveat 6.1) must not be presented as
decisive.

**What this resolves from the claim audit.** CLAIM_AUDIT_SMOLVLA §"Does not
rule out" left open that the 9 unmeasured tasks per suite could each score
high enough to recover the published averages. They do not. The deferred
apples-to-apples comparison now exists, and the deck/paper headline can be
upgraded from the envelope phrasing ("at least one task scores well below…")
to a suite-averaged claim for **spatial, object, and libero_10** — with the
step-cap caveat travelling wherever the headline lands (as a slide/table
footnote, per the CLAIM_AUDIT_SMOLVLA §7 pattern), since the cap confound is
one-directional and unprobed on 3 of 4 suites (caveat 6.1). **Goal should be
excluded from any headline** (or conditioned on the cap-600 probe, §8): its
gap is the smallest, its adjusted p is marginal (0.037), and its 300-vs-600
cap is the kind of confound that could plausibly account for a large fraction
of −10.7 pp.

## 2. Per-task rates

Each cell: 5 seeds × 50 episodes = 250. Wilson half-width ≈ ±0.06 at p=0.5,
shrinking toward the extremes.

| Suite \ task | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|---|
| libero_spatial | 0.800 | 0.772 | 0.784 | 0.784 | 0.472 | **0.036** | 0.880 | 0.732 | 0.580 | 0.592 |
| libero_object | 0.524 | 0.744 | 0.548 | 0.596 | 0.856 | 0.408 | 0.860 | 0.764 | 0.816 | 0.720 |
| libero_goal | 0.924 | 0.956 | 0.872 | 0.680 | 0.844 | 0.804 | 0.548 | 0.916 | 0.812 | 0.772 |
| libero_10 | 0.244 | 0.524 | 0.808 | 0.864 | 0.240 | 0.728 | 0.288 | 0.296 | 0.388 | 0.548 |

Within-suite task heterogeneity is large everywhere (spread 0.41–0.84), which
is itself the strongest argument against ever reporting single-task numbers as
suite proxies.

**`libero_spatial_t5` = 0.036 (9/250) is a near-total single-task failure** —
an order of magnitude below every other spatial task. Excluding it, the
spatial suite average is 0.711 (1599/2250), still −18.9 pp below published, so
the spatial gap is *not* explained by this one outlier — but t5 deserves a
failure-taxonomy pass (videos in `results/sweep-v11-libero/videos/`).

## 3. Was task 0 representative? (v1's envelope, graded)

| Suite | task-0 rate | suite avg | task-0 percentile in suite |
|---|---|---|---|
| libero_spatial | 0.800 | 0.643 | above avg (2nd of 10) |
| libero_object | 0.524 | 0.684 | below avg (9th of 10) |
| libero_goal | 0.924 | 0.813 | above avg (2nd of 10) |
| libero_10 | 0.244 | 0.493 | 9th of 10, one episode above the hardest (t4, 0.240) |

v1's single-task reads were *individually* honest but *directionally
unrepresentative* in both directions: the v1 libero_10 headline (−45.8 pp on
task 0) **overstated** the suite-level gap (−21.7 pp) because task 0 is
essentially the hardest LIBERO-10 task, while v1's spatial/goal task-0 reads
**understated** their suite gaps. This is precisely the failure mode the
claim audit predicted; the softened v1 phrasing (PR #91) was the right call.

## 4. Replication: v1 task-0 cells reproduce a month later

The 4 bare-suite envs are the same (policy, env, seed-set, criterion) cells v1
ran in `results/sweep-full/results.parquet` (2026-05-22). v1.1 re-measured
them from scratch (fresh rollouts: goal/libero_10 in June under `10156cf`,
spatial/object in July under `cd5e961` — two of the parquet's four shas):

| Env | v1 (n=250) | v1.1 (n=250) | Δ |
|---|---|---|---|
| libero_spatial | 0.776 [0.720, 0.823] | 0.800 [0.746, 0.845] | +2.4 pp |
| libero_object | 0.528 [0.466, 0.589] | 0.524 [0.462, 0.585] | −0.4 pp |
| libero_goal | 0.928 [0.889, 0.954] | 0.924 [0.884, 0.951] | −0.4 pp |
| libero_10 | 0.252 [0.202, 0.309] | 0.244 [0.195, 0.301] | −0.8 pp |

All four deltas are within ±2.4 pp with fully overlapping CIs. This is the
strongest internal-replication evidence the bench has: the eval contract is
stable across a month of wall time, harness commits, and sweep restarts (RQ2
material).

## 5. Seed stability

Per-seed suite-level rates vary by ≤ 4.0 pp across the 5 seeds (libero_10:
range 1.0 pp). Episode-level Wilson CIs therefore aren't hiding meaningful
seed-cluster variance at suite granularity.

## 6. Caveats — what "the gap survives" does and does not claim

1. **This is a protocol-level discrepancy, not a "SmolVLA is worse than
   reported" claim.** Known residual protocol differences: our 5 seeds × 50
   episodes vs. their 10 trials/task (initial-state distributions may differ);
   our v1_legacy step caps (spatial/object=280, goal=300, libero_10=520) vs.
   canonical 600. The cap axis was probed on `libero_10` task 0 only
   (+0.4 pp at cap=600, `PROBE_RESULTS_V1.0.1.md` Probe 2) — small there, but
   **unprobed for the other three suites**, whose caps are tighter relative to
   canonical. **The cap confound is one-directional**: a tighter cap can only
   censor would-be successes, so it can only widen our measured gap, never
   shrink it — which is why it must travel with the headline wherever the
   headline lands. The LIBERO success *rule* is bit-equivalent
   (`SUCCESS_CRITERION_AUDIT.md`); inference settings were audited
   (`INFERENCE_AUDIT.md`).
2. **Episode-level tests (Wilson CIs, Fisher) assume iid episodes and are
   anticonservative by orders of magnitude here** — the task-level design
   effect is 25–65×. This is why §1's primary test uses the task as the
   sampling unit; the conclusion rests on that analysis (all four suites
   still reject), not on the episode-level intervals, which are retained
   only as descriptive summaries. Seed-level stability (§5) addresses seed
   clustering only and says nothing about task clustering.
3. **Published numbers are n=100 self-reports** — we cannot audit their
   per-task breakdown (Table 2 releases suite scalars only), so a
   task-paired comparison is not possible.

## 7. Provenance

Four `code_sha` values span the parquet (sweep started 2026-06-13, resumed
2026-07-06 after a pause, finished 2026-07-08):

| code_sha | envs touched | rows | window |
|---|---|---|---|
| `10156cf` | 14 | 3,350 | 2026-06-13 → 06-16 |
| `4587785` | 1 | 50 | 2026-07-06 |
| `a945e4c` | 1 | 50 | 2026-07-07 |
| `cd5e961` | 27 | 6,550 | 2026-07-07 → 07-08 |

All four are ancestors of `main`. The measurement path is unchanged across
them: `src/embodimetry/{eval,envs,policies}.py` have zero diff
`10156cf..cd5e961`, `configs/envs.yaml` changes are comment-only, and the
`run_one.py`/`checkpointing.py` diffs are log-line and duplicate-validation
changes (verified 2026-08-06). §4's cross-sha replication is the empirical
check that the measurement didn't drift. **Publish implication:**
`scripts/publish_results.py`'s provenance guard requires a single parquet-wide
`code_sha`, so this dataset hits the same guard as v1 — same decision
(documented override vs. re-run) applies if/when v1.1 publishes.

## 8. Follow-ups

- [ ] Failure-taxonomy pass on `libero_spatial_t5` (0.036) and the
      libero_10 hard cluster (t0/t4/t6/t7 all ≤ 0.30).
- [ ] Canonical-cap (600) probe for spatial/object/goal to close caveat 6.1.
- [ ] Upgrade deck slide 07 / paper headline from the envelope phrasing to the
      suite-averaged comparison for spatial/object/libero_10, cap caveat as a
      footnote; goal excluded until the cap-600 probe (editorial — Théo).
- [ ] CHANGELOG `[Unreleased]` entry + decide whether v1.1 results publish to
      the Hub (blocked on the same code_sha decision as v1).
