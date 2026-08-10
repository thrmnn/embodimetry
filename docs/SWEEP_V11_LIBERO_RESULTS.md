# v1.1 LIBERO 10-task sweep results

> **Status: ANALYZED + stats-rigor reviewed (2026-08-06); goal cap-600 probe
> added 2026-08-07 (§8).** The review's veto (episode-level Fisher test invalid
> under task clustering) and all must-fix findings are incorporated below — the
> primary test is task-as-sampling-unit. The goal suite's cap confound is now
> **empirically closed**: doubling the cap to canonical 600 moved the suite
> average by exactly 0.0 pp. Sweep completed
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
goal gap must be framed as the smallest and statistically marginal, though
its cap confound has since been probed and closed (§8: suite average
identical at cap 600, one-sample task-level p = 0.026 at the canonical cap).

**What this resolves from the claim audit.** CLAIM_AUDIT_SMOLVLA §"Does not
rule out" left open that the 9 unmeasured tasks per suite could each score
high enough to recover the published averages. They do not. The deferred
apples-to-apples comparison now exists, and the deck/paper headline can be
upgraded from the envelope phrasing ("at least one task scores well below…")
to a suite-averaged claim for **all four suites** — with the step-cap caveat
travelling wherever the headline lands (as a slide/table footnote, per the
CLAIM_AUDIT_SMOLVLA §7 pattern) for spatial/object, whose 280 caps remain
unprobed (caveat 6.1). **Goal's original exclusion is lifted** (2026-08-07):
the cap-600 probe (§8) shows its suite average is numerically unchanged at
the canonical cap (same success count, 2032/2500), so the −10.7 pp gap is
not cap-induced — but goal stays
labeled as the smallest gap with marginal significance (adjusted p = 0.037
in-family; p = 0.026 at the canonical cap), never as decisive.

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
   headline lands. Probed and closed for **goal** (§8: +0.0 pp at cap 600)
   and for **libero_10 task 0** (+0.4 pp, `PROBE_RESULTS_V1.0.1.md` Probe 2);
   still unprobed for spatial/object (cap 280). With stuck-while-trying now
   replicated on two suites (goal: full suite at 2× cap; libero_10: task 0
   only, 520→600), a large cap effect on spatial/object is implausible — but
   that is a judgment, not a measurement, so the caveat stays. The LIBERO success *rule* is bit-equivalent
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

## 8. Goal-suite canonical-cap probe (added 2026-08-07)

Motivation: 100% of v1.1 failures run to the v1_legacy step cap in every
suite (§6.1), so the cap confound was unbounded from that data alone — and
goal's 300-vs-600 cap was the stated reason for excluding it from headlines.
Probe: the full goal suite re-run under the canonical overlay (`criterion:
canonical`, max_steps=600), same protocol otherwise (10 tasks × 5 seeds × 50
eps = 2,500 episodes, ~13.8 h). Config `configs/probe_v11_goal_cap600.yaml`,
data `results/probes/sweep-v11-goal-cap600/results.parquet` (0 errored; two
code_shas, `d15f078`/`90bf6cb` — the latter only adds the probe config
itself).

**Result: doubling the cap leaves the suite average unchanged and bounds the
cap effect at ≲1.4 pp.** Suite average at cap 600 is **0.813 (2032/2500)** —
the same success count as cap 300. (The identity is aggregate, not
episode-level: the runs are not episode-deterministic, and 237 episodes
flipped in each direction between them.) Per-task deltas span −2.0 to
+1.2 pp, mean −0.0 pp — consistent with noise (paired task-level t p = 1.00,
Wilcoxon p = 0.95; 95% CI on the mean cap effect from the paired deltas
[−0.8, +0.8] pp). Failures riding to the cap is structural in LIBERO
(episodes end only on success or cap), so the discriminating evidence is the
success-time distribution: only **35/2,032 successes needed more than 300
steps** (1.4 pp of episodes; P99 = 374, max = 567 of 600) — the directly
observed censoring tail caps the cap effect at 1.4 pp, an order of magnitude
below the 10.7 pp gap. The policy is **stuck-while-trying**, not
slow-but-eventually-correct, replicating the libero_10 task-0 cap probe
(+0.4 pp) at 10× the task coverage.

| Task | cap 300 | cap 600 | Δ pp |
|---|---|---|---|
| t0 | 0.924 | 0.928 | +0.4 |
| t1 | 0.956 | 0.960 | +0.4 |
| t2 | 0.872 | 0.884 | +1.2 |
| t3 | 0.680 | 0.692 | +1.2 |
| t4 | 0.844 | 0.848 | +0.4 |
| t5 | 0.804 | 0.788 | −1.6 |
| t6 | 0.548 | 0.540 | −0.8 |
| t7 | 0.916 | 0.924 | +0.8 |
| t8 | 0.812 | 0.792 | −2.0 |
| t9 | 0.772 | 0.772 | +0.0 |

**Verdict — and the load-bearing argument is the direct measurement, not the
paired null:** the gap is now measured *at the canonical cap itself* — 0.813
vs published 0.92, one-sample task-level t p = 0.026 (unadjusted; single
planned comparison), cluster-robust 95% t-CI [0.722, 0.904] excludes 0.92,
Cohen's h = 0.32 — so the counterfactual "would cap 600 have closed it"
question is moot. **The goal gap is not cap-induced; caveat 6.1 is closed
for goal, and goal's headline exclusion is lifted** (still framed as the
smallest, statistically marginal gap). Per-seed suite rates at cap 600 stay
within a 4.0 pp band (0.796–0.836), matching §5.

## 9. Follow-ups

- [x] ~~Canonical-cap (600) probe for goal~~ — done, §8 (2026-08-07): +0.0 pp,
      confound closed for goal.
- [x] ~~Failure-taxonomy pass on `libero_spatial_t5` (0.036) and the
      libero_10 hard cluster~~ — done, §10 (2026-08-10): 62 labeled
      episodes, `assets/failure-taxonomy-labels-v11.csv`.
- [ ] Canonical-cap probe for spatial/object (cap 280) — lower priority now
      that stuck-while-trying is replicated on two suites, but it's what
      would let the cap footnote drop entirely.
- [ ] Upgrade deck slide 07 / paper headline from the envelope phrasing to the
      suite-averaged comparison for all four suites; cap footnote for
      spatial/object; goal labeled marginal (editorial — Théo).
- [ ] CHANGELOG `[Unreleased]` entry + decide whether v1.1 results publish to
      the Hub (blocked on the same code_sha decision as v1).
- [ ] `PROBE_RESULTS_V1.0.1.md` Probe 2 leans on the same "cap-hits stay
      high" framing §8 had to drop as tautological (LIBERO failures can only
      end at the cap) — its conclusion stands via its Δ+0.4 pp, but the
      framing deserves the same success-time-tail rewrite.
## 10. Failure taxonomy on the outlier cells (added 2026-08-10)

Closes the §9 follow-up: a per-episode labeling pass on `libero_spatial_t5`
(0.036, 9/250 — the headline outlier) and the libero_10 hard cluster
(t0 0.244, t4 0.240, t6 0.288, t7 0.296). This is the per-episode upgrade
`FAILURE_TAXONOMY.md` §"How to upgrade" gated on: labels are joined on
`(policy, env, seed, episode_index)` against the per-episode parquet, and
each labeled episode's video was inspected as a 12-keyframe montage
(evenly spaced over the episode) plus targeted zooms/densifications where
the montage was ambiguous. Labels:
[`assets/failure-taxonomy-labels-v11.csv`](assets/failure-taxonomy-labels-v11.csv)
(60 failures + 2 success references; same schema as the v1 CSV).

**Sampling rule (deterministic, no RNG).** Per cell: order each seed's
*failed* episodes by ascending `episode_index`; select round-robin across
seeds 0–4, taking each seed's k-th earliest failure at pass k, until 12 are
selected (≥2 per seed). For spatial_t5's success side: the earliest success
of each of the two lowest-numbered seeds (seed0 ep009, seed1 ep009). Single
labeler, no agreement statistic — same caveat as the v1 pass. Counts below
are observational; at n=12 per cell no within- or cross-cell rate claims
are made beyond the raw counts.

### Per-cell modes (n = 12 failures each)

| Cell | Dominant mode | Count | Other modes |
|---|---|---|---|
| libero_spatial_t5 | place-off-target (bowl released tilted/half-on the plate rim or away from the plate) | 7/12 | grasp-never-secured at the elevated bowl 4/12; wrong-object (ramekin ends on the plate) 1/12 |
| libero_10 (t0) | hover-stall, no grasp (quasi-static above a can to the 520 cap) | 6/12 | first can delivered then stall on the second 5/12; transport-drop-short 1/12 |
| libero_10_t4 | slip-lost-mug (white mug slips out mid-transport, lost from view) | 4/12 | paw-stall at first mug, no lift 4/12; second mug deposited on the wrong plate 3/12; holds mug over a plate at cap, never releases 1/12 |
| libero_10_t6 | pudding-related stall | 10/12 | of which: mug-on-plate completed first 5, nothing completed 5; wrong-object engagement with the red distractor mug 2/12 |
| libero_10_t7 | cream-cheese paw-stall (repeated failed grasps at the small box, nothing placed) | 8/12 | soup delivered then stall 1/12; grasps and lifts the BASKET itself 1/12; holds the box over the basket at cap 1/12; ambiguous 1/12 |

Ambiguity stayed under the 1/3 threshold everywhere (worst cell: t7, 1/12
forced to `ambiguous` — the cream-cheese box vanishes from agentview and
may have been pushed into the basket).

### The spatial_t5 story

spatial_t5 ("pick up the black bowl **on the ramekin** and place it on the
plate") is **not** a stall cell. In all 12 labeled failures the policy runs
the full pick-and-place routine; it fails at one of the two contact-rich
ends:

- **Grasp end (4/12):** the fingers close on or above the elevated
  bowl-on-ramekin stack without securing it (zoom-verified). Twice the
  attempt knocks the bowl off — once flipping it upside-down beside the
  ramekin. Notably, after a failed grasp the arm **executes the transport
  and place motion anyway with an empty gripper**, paws at the plate, then
  cycles back to re-attempt — repeating until the 280 cap.
- **Place end (7/12):** grasp and transport succeed, but the bowl is
  released at the plate's rim — tilted, half-on, or leaning against the
  adjacent distractor bowl — and the `On(bowl, plate)` predicate never
  fires. In two of these the bowl looks essentially "on the plate" to the
  eye yet stays rim-balanced/tilted at cap; the policy keeps poking at it
  without re-seating it. One further episode (counted separately as
  wrong-object) ends with the **ramekin** on the plate and the bowl gone
  from view.

**What the 9 successes do differently** (2 of 9 viewed: seed0 ep009 at 118
steps, seed1 ep009 at 116 steps — near-identical trajectories): a single
clean grasp that lifts the bowl off the ramekin on the first attempt
(~step 50), a short hover holding it, then a direct transport and a
**centered, flat** placement on the plate. Same routine as the failures —
the successes differ only in securing the first grasp and seating the bowl
inside the rim rather than on it. Both viewed successes finish in <45% of
the step cap, consistent with the cell's failure mass being grasp/place
execution rather than time pressure.

### Cross-cell pattern (observational)

1. **Failures ride to the cap in an active near-stationary state.** All 60
   labeled failures end at the step cap (consistent with §6.1: 100% of
   v1.1 failures are cap-terminated) with the gripper *at or hovering over
   a task-relevant object* — pawing, pressing, or holding — not drifting
   away or freezing off-task. "Stuck-while-trying" (§8) is what it looks
   like frame-by-frame.
2. **The four libero_10 hard cells are all two-object composites, and the
   sampled failures concentrate on one leg of the composite.** In 11/48
   labeled episodes the first object is delivered and the episode stalls
   on the second; in most of the rest the stall happens on the first
   object. The stall target is disproportionately a **small/low-profile
   object** — the pudding box (t6, 10/12) and the cream-cheese box (t7,
   9/12 incl. the held-at-cap episode) absorb nearly all of those cells'
   failure time.
3. **Distractor/wrong-object behavior recurs at low rates but in every
   scene that has a distractor:** terminal hovering over the red patterned
   mug in t4 (7/12 labeled episodes end there; it is never a task target),
   red-mug engagement in t6 (2/12), the ramekin-on-plate episode in t5
   (1/12), and — most strikingly — one t7 episode that grasps and lifts
   **the basket itself** and holds it tilted in mid-air at cap.
4. **Two episodes end with the target object gripped, held in place and
   never released** (t4 s3e001 over the wrong plate; t7 s3e002 over the basket) —
   a place-commitment failure distinct from both slip and stall.

No causal claim is attached to any of these: the labels say what the
rollouts show, not why the policy does it.

### Method notes / artifacts

- Keyframe protocol: 12 evenly spaced frames per episode (4×3 montage),
  plus zoomed crops (grasp windows, basket interiors, terminal frames)
  where the montage was ambiguous. This exceeds the 4–6 keyframes the
  original protocol sketch suggested; the denser grid was necessary to
  separate slip from no-lift and in from at-rim.
- **Video off-by-one quirk (worth knowing for any future labeling):** in
  success-terminated episodes the *last* video frame is the **next
  episode's post-reset frame**, not the terminal state (verified:
  spatial_t5 seed0 ep009 frame 118 is pixel-identical to ep010 frame 0).
  The true terminal state is the penultimate frame. Cap-terminated
  (failure) videos end on the true terminal observation.
- Labels are single-view (agentview only; the wrist camera is not in the
  rendered videos), so in/at-rim judgments near occlusions carry
  irreducible uncertainty — flagged per-row in the CSV notes.
