# Claim audit — SmolVLA published vs measured success rates

| Field   | Value |
| ------- | ----- |
| Status  | Open |
| Date    | 2026-05-26 |
| Auditor | researcher (audit/v1.0.1-smolvla-task-id) |
| Pipeline-roadmap item | §1.1 |
| Verdict | **Hard mismatch — the deck and paper headline phrasing have to change.** The paper-reported SmolVLA LIBERO rates are *per-suite averages over all 10 tasks × 10 trials = 100 episodes*. We ran *task_id=0 × 250 episodes* per suite. The two numbers are not measuring the same quantity, so the "−45.8 pp gap" is not a defensible apples-to-apples claim. It is at best an *envelope* claim ("at least one of the 10 LIBERO-10 tasks scores 0.252 against the suite-average 0.71"). |

## 1. One-sentence finding

Per SmolVLA paper §4.1 "Simulated environments" (Shukor et al. 2025, arXiv:2506.01844, p. 8), the Table 2 LIBERO numbers ([Spatial 90, Object 96, Goal 92, Long 71] for the 0.45B variant we evaluate) are the average across **all 10 tasks per suite × 10 trials per task** — `lerobot-bench` v1 runs only `task_id=0` × 5 seeds × 50 episodes per suite, so a head-to-head claim against the published 0.71 is statistically incoherent until v1.1 widens our task coverage.

## 2. Sources traced

| Cited rate | Cited in | Original source | Verified ✓ |
| ---------- | -------- | --------------- | ---------- |
| SmolVLA `libero_spatial` 0.90 | `configs/policies.yaml` L184–196, `paper/main.tex` Headline-finding paragraph, deck slide 06–09 | Shukor et al. 2025, [arXiv:2506.01844](https://arxiv.org/abs/2506.01844) Table 2, row "SmolVLA (0.45B), VLA Pt. = No" | ✓ |
| SmolVLA `libero_object` 0.96 | ditto | ditto | ✓ |
| SmolVLA `libero_goal` 0.92 | ditto | ditto | ✓ |
| SmolVLA `libero_10` 0.71 ("Long") | ditto + deck slide 07 headline "0.71" | ditto | ✓ |
| Pi0 (0.45B-paligemma) LIBERO baseline | (informational only, not a v1 cell) | ditto | ✓ |

The HF model card for `lerobot/smolvla_libero` ([README.md raw](https://huggingface.co/lerobot/smolvla_libero/raw/main/README.md), retrieved 2026-05-26) **does not report any LIBERO success rate of its own** and does not state an eval protocol. It is a thin LeRobot training-recipe stub that points at the SmolVLA paper as the canonical reference. The only authoritative source for the four numbers is therefore the SmolVLA paper's Table 2.

## 3. SmolVLA paper protocol (verbatim)

From §4.1 "Simulated environments", p. 8 (emphasis added):

> "LIBERO assesses diverse visuomotor skills across four categories—*Spatial, Object, Goal,* and *Long*—with **10 tasks per category (40 total)**. We use a dataset (Kim et al., 2024; Pertsch et al., 2025) containing 1,693 episodes covering all tasks, and **evaluate with 10 trials per task, reporting average success rates based on binary completion criteria**."

From §4 "Evaluation metrics":
> "For simulation-based evaluations, SR is binary—set to 1 if the task is successfully completed, and 0 otherwise."

From §4.3 "Implementation details" (inference-time settings disclosed):
> "The action expert is trained with flow matching to output chunks of n = 50 actions. … In simulation, we perform inference by sampling new observations and predicting a new action after each executed action. During inference, the flow matching is fixed to 10 steps. We train only the action expert module, keeping the VLM frozen."

From Table 13 ("Action execution steps"): the paper trains and reports with `Action Steps = 1`, i.e. **re-plan every env step** ("Sampling new observations every 1 or 10 steps significantly improves performance"). Chunk size 50 with `n_executed=1` is the disclosed regime; the LIBERO Table 2 row is implicitly that regime.

Summary of the paper's protocol per cell:

| Field | SmolVLA paper |
| ----- | ------------- |
| Tasks per suite | **All 10** (mirrors LIBERO benchmark structure) |
| Trials per task | 10 |
| **Episodes per suite** | **100** (= 10 × 10) |
| Seeds | Not explicitly stated; "10 trials per task" replaces a multi-seed × N-episode contract |
| Success metric | Binary, task fully completed |
| Action chunk size n | 50 |
| Executed actions before re-plan | 1 (every step) |
| Flow-matching denoise steps | 10 |
| Inference mode | Synchronous (sim only — async is real-world only per §4.6) |

## 4. Our protocol (lerobot-bench v1)

Per `configs/envs.yaml` libero entries, `configs/policies.yaml` SmolVLA entry, and `src/lerobot_bench/eval.py`:

| Field | lerobot-bench v1 |
| ----- | ---------------- |
| Tasks per suite | **`task_id=0` only** (one task — the canonical first task per suite) |
| Trials per task | 250 (5 seeds × 50 episodes) |
| **Episodes per suite** | **250** |
| Seeds | 5 (`seed_idx ∈ {0,1,2,3,4}`, base seed = `seed_idx × 1000`, per-episode seed = `base + episode_index`) |
| Success metric | Binary, `final_reward ≥ env_spec.success_threshold = 1.0` for LIBERO |
| Action chunk size n | Whatever the Hub checkpoint config declares (unaudited here; almost certainly `n=50` matching paper, but not verified for this audit) |
| Executed actions before re-plan | Implicit in `lerobot`'s `select_action`; the bench does not override |
| Flow-matching denoise steps | Default; unaudited here |
| Inference mode | Synchronous (one `select_action` per env step in `run_cell`) |

## 5. Per-cell mismatch table

| Cell | Paper-reported | Our measured | Δ (paper − ours) | Apples-to-apples? | Severity |
| ---- | --------------:| ------------:| ----------------:| ----------------- | -------- |
| `smolvla × libero_spatial` | 0.90 (suite-avg) | 0.776 [0.720, 0.823] | −12.4 pp | **No** — paper averages 10 tasks, we ran 1 | **Soft** — direction plausibly meaningful, magnitude not interpretable |
| `smolvla × libero_object`  | 0.96 (suite-avg) | 0.528 [0.466, 0.589] | −43.2 pp | **No** — same averaging mismatch | **Hard** — gap could be entirely explained by task-0 being the hardest of 10, or could be a real regression; we cannot tell |
| `smolvla × libero_goal`    | 0.92 (suite-avg) | 0.928 [0.889, 0.954] | +0.8 pp | **No** — same averaging mismatch | **Soft** — coincidentally close; "matches" claim is unsupported (could be task-0 is easier than average) |
| `smolvla × libero_10`      | **0.71** (suite-avg) | **0.252 [0.202, 0.309]** | **−45.8 pp** | **No** — same averaging mismatch | **Hard** — headline claim on deck slide 07; cannot stand as written |

In all four cases the published number is a single scalar summarising 100 binary outcomes across 10 distinct tasks, while ours is a single scalar summarising 250 binary outcomes on 1 task. The MDE argument that "Wilson half-width 0.054, the gap is not sampling noise" is correct for the proposition "task 0 measures 0.252" but **not** for the proposition "the suite-averaged rate is 0.252". The latter is what the comparison to 0.71 implicitly claims, and that proposition is unidentified at our `task_id=0`-only coverage.

## 6. What this rules in / out

- **Rules in:** the *headline gap on task 0* is real and large. SmolVLA at `libero_10 task_id=0` is empirically 0.252 [0.202, 0.309] over 250 episodes; that fact is bit-reproducible from `thrmnn/lerobot-bench-v1` and not in dispute.
- **Rules out:** the claim "SmolVLA on libero_10 measures 0.252, not the paper-reported 0.71". This is not a defensible apples-to-apples comparison until either (a) we run all 10 tasks per suite at our protocol, or (b) the SmolVLA authors release per-task numbers we can compare task 0 against. Currently the paper releases only suite-averaged rates in Table 2.
- **Does not rule out:** that the gap *survives* averaging over all 10 tasks. It's entirely possible that v1.1 finds suite-averaged SmolVLA × libero_10 ≈ 0.3–0.5 (still well below 0.71); the bound from a single task is `0.1 × 0.252 + 0.9 × <unknown>` where the unknown 9 tasks could in principle each score 1.0, putting the suite average at ≤ 0.925. The arithmetic permits the published 0.71 *and* permits a real gap.

## 7. Recommended deck / paper changes

### Slide 06 ("paper numbers vs measured")
Add a footnote to the table caption: *"Paper rates are suite-averaged over all 10 tasks per LIBERO suite × 10 trials per task (Shukor et al. 2025 §4.1). Our measured rates are `task_id=0` × 5 seeds × 50 episodes. Direct numerical comparison is not apples-to-apples at v1; see slide 08."*

### Slide 07 (headline 0.71 vs 0.252)
Reframe from:
> "SmolVLA on libero-10: 0.71 paper → 0.252 measured. −45.8 pp gap."

To one of:
- **(preferred, defensible)** "SmolVLA on **libero_10 task 0**: 0.252 [0.202, 0.309] over 250 episodes. The paper reports 0.71 *averaged across all 10 tasks*, not per-task — the suite-averaged comparison is deferred to v1.1."
- **(softer, frames the question)** "At least one of the 10 LIBERO-10 tasks scores 0.252 over 250 episodes — well below the suite-averaged 0.71. v1.1 runs all 10 tasks per suite to resolve whether the suite-average gap survives."

### Slide 08 (open questions)
The task-coverage item moves from "audit question" to "**confirmed apples-to-oranges; v1.1 ticket**". The other three items (inference settings, external replication, hardware variance) remain open.

### `paper/main.tex` Headline-finding paragraph (lines 361–390)
Same substantive change as slide 07. Specifically delete:
> "SmolVLA on LIBERO-10 measures 0.252, not the paper-reported 0.71."

Replace with:
> "SmolVLA at `libero_10 task_id=0` measures 0.252 [0.202, 0.309]. The SmolVLA paper reports a suite-averaged 0.71 across all 10 LIBERO-10 tasks; v1's single-task coverage does not support a direct apples-to-apples comparison to that number, but does establish that at least one of the 10 tasks scores well below the published average. Per-task replication is deferred to v1.1."

The MDE argument and the hypothesis pair (a)/(b) survive as currently written — the MDE establishes the per-task measurement is not noise. The text should additionally cite the SmolVLA §4.1 protocol verbatim (10 trials per task × 10 tasks).

### `configs/policies.yaml` SmolVLA `paper_reported_notes` (lines 188–196)
Update the protocol description from:
> "Paper protocol: 10 trials per task, scored binary (1 only if task is fully completed). Our re-run uses 5 seeds × 50 episodes per cell, which is roughly 5× more rollouts; CI width should be smaller than the paper's."

To:
> "Paper protocol: **10 trials per task × 10 tasks per suite = 100 episodes per suite-averaged rate**, scored binary (1 only if task is fully completed) — Shukor et al. 2025 §4.1. Our v1 re-run uses 5 seeds × 50 episodes on `task_id=0` only = 250 episodes per single-task rate. The two protocols measure different quantities (suite-average vs single-task); see `docs/CLAIM_AUDIT_SMOLVLA.md` for the apples-to-apples discussion. v1.1 expands to all 10 tasks per suite."

### `docs/PIPELINE_ROADMAP.md` §1.1
Mark item §1.1 as **resolved with verdict: hard mismatch**, with this audit as the artifact. Promote "expand `task_ids` to all 10 per suite" from a v1.1 nice-to-have to a v1.1 **blocker** for any republished headline claim.

## 8. Same audit applied to XVLA (deferred policy)

`configs/policies.yaml` cites XVLA Table 2 (Bu et al. 2025, arXiv:2510.10274) for `libero_*` numbers (Spatial 98.2 / Object 98.6 / Goal 97.8 / Long 97.6 for the 0.9B variant). The XVLA paper **does not state an episode count for LIBERO eval** — it cites the LIBERO benchmark inheritance. By the same SmolVLA/OpenVLA-paper convention these are almost certainly 10 trials × 10 tasks = 100-episode suite averages. The XVLA cells are already deferred to v1.1 for an unrelated reason (Hub-JSON wiring bugs, see `docs/DEFERRED_POLICIES.md`); the apples-to-oranges mismatch is the same and the v1.1 fix is the same single ticket (expand `task_ids`).

## 9. Other audited claims that are NOT affected

For completeness, the cells whose paper-reported sources we re-checked but where no protocol mismatch exists:

- **Diffusion Policy × pusht 0.654** — sourced from the **LeRobot Hub model card** for `lerobot/diffusion_pusht`, evaluating the exact pinned revision on 500 episodes with the binary metric. That is our metric (final-reward ≥ 0.95). Same protocol family. No change needed. (The Chi et al. 2023 paper's 0.91 number uses target-area coverage, not binary success, and is explicitly noted in the YAML as not comparable.)
- **ACT × aloha_transfer_cube 0.50** — sourced from Zhao et al. 2023 Table I, human-teleop training column, 3 seeds × 50 evaluations. Our protocol (5 seeds × 50 episodes) is the same shape with more rollouts. No change needed.

## 10. Open questions we cannot close without contacting authors

1. **Per-task SmolVLA rates.** The paper releases only suite averages. Until the SmolVLA authors release per-task numbers (or the training script's per-task eval logs), we cannot directly compare our `task_id=0` rate to the paper's task-0 rate — only to the all-10 average. *Mitigation:* file a polite issue on the SmolVLA GitHub asking for the per-task breakdown of Table 2. *Cost if unanswered:* we run all 10 ourselves in v1.1 — that's the budgeted plan anyway.
2. **Action-chunk inference settings.** The paper's Table 13 shows performance is highly sensitive to `Action Steps` (re-plan frequency), with `n_executed=1` recommended; the 0.45B/SmolVLA row in Table 2 implicitly uses the recommended setting. We do not explicitly set this in `eval.py`; it inherits whatever the Hub checkpoint config declares. *Mitigation:* a separate audit item to verify `select_action` in lerobot 0.5.1's SmolVLA path executes the recommended chunk-prefix-of-1 regime. If it executes `n_executed=50` (full chunk) instead, the gap could shrink materially even on task 0 — Table 13 reports `Action Steps = 50` collapses to 25 average on libero_long vs 53 at `Action Steps = 1`. **This is the second-most-likely audit hit after task coverage and should be investigated before v1.1 publishes new headline numbers.**
3. **Multi-seed contract.** The paper does not state how many seeds it uses for the 10 trials per task. If "10 trials" means 1 seed × 10 episodes per task, the published 0.71 is itself a thin number with no CI — and the criticism cuts both ways (we report a tighter interval on one task; they report a wider interval averaged over many). Mention this in the deck reframing.
4. **Hub-checkpoint training-data overlap with task 0.** The `lerobot/smolvla_libero` checkpoint is `lerobot/smolvla_base` finetuned on `lerobot/libero` — which itself is built from the LIBERO dataset (Kim et al. 2024; Pertsch et al. 2025). It is plausible that task 0 of each suite has different demo coverage than tasks 1–9, which would couple our `task_id=0`-only protocol to a training-data bias. *Mitigation:* same v1.1 ticket — running all 10 tasks resolves this too.

---

*This audit is the artifact for `docs/PIPELINE_ROADMAP.md` §1.1. PR branch: `audit/v1.0.1-smolvla-task-id`. User-reviewed; do not auto-merge.*
