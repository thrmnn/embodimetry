---
status: draft
depends_on: []
---

# Proposal — embodimetry

> Reconstructed from the existing `paper/main.tex` (abstract + intro + related
> work), not written from a blank page — a full draft already exists. This is
> the retroactive DAG entry point: review it first, since `results.md`,
> `figures.md`, `lit-review-detail.md`, and `targets.md` all depend on the RQs
> and gaps locked here matching what the draft actually argues.

## Working title

*embodimetry: a Capability-Ladder Audit — measuring pretrained, fine-tuned,
and classical robot policies on one reproducible eval contract*

**Open question for review:** the title names pretrained/fine-tuned/classical
but not the world-model rung (L3), even though the abstract's third
contribution — the nav-vs-contact replication — is a headline result. Worth
deciding whether the title should name L3 explicitly or stays paradigm-neutral
on purpose (the ladder framing already implies "and beyond").

## Research questions

1. **RQ1 (the contract).** Can pretrained, fine-tuned, classical-control, and
   world-model-planning policies be scored on one shared, statistically
   rigorous eval contract — same seed accounting, same Wilson/bootstrap-CI,
   same MDE bound — despite each paradigm normally being benchmarked in
   isolation on incompatible protocols?
2. **RQ2 (the self-audit).** Can an eval harness's credibility rest on
   catching and correcting *its own* bugs, not just on the numbers it
   reports? (Answered via the ACT×aloha normalization bug: 0.016 → 0.824.)
3. **RQ3 (the dynamics-complexity question — the paper's animating
   question).** Does a zero-training world-model latent-MPC planner's
   success track the dynamical complexity of the environment — does it
   solve navigation but not contact, and does that split replicate across
   independent world-model families?
4. **RQ4 (secondary — the middle rungs).** Under the same MDE-bounded
   contract, where does continued fine-tuning (L1) or a competent classical
   controller (L2) move the needle relative to a strong pretrained baseline?

## The gap each RQ addresses

- **RQ1 gap:** PushT, Aloha, LIBERO, RLBench, CALVIN, and Open X-Embodiment
  are the standard references, but none ship a multi-policy leaderboard with
  shared seed accounting, multi-seed CIs, and re-runnable rows across
  paradigms. Cross-paradigm comparisons are always informal.
- **RQ2 gap:** No neighboring benchmark treats its own harness as an audit
  target. Eval suites report policy failures; they don't report and correct
  their *own*.
- **RQ3 gap:** World-model planners (PlaNet, DINO-WM, V-JEPA-2-AC) report
  success only on their own tasks, never against a learned imitation policy
  under one shared seed/CI protocol — so "when does planning substitute for
  learning" has never been measured on a ruler that also holds a policy
  baseline.
- **RQ4 gap:** L1/L2 rungs are usually reported as wins; the contract's
  honesty bar requires reporting them as within-noise or as a bug-driven
  collapse when that's what the data says.

## Lit review method

- **Venues:** arXiv cs.RO / cs.LG, plus CoRL / ICRA / RSS / NeurIPS
  (Datasets & Benchmarks track) proceedings.
- **Keywords:** "robot policy benchmark", "multi-seed robot learning
  evaluation", "world model planning manipulation", "Wilson confidence
  interval reinforcement learning", "minimum detectable effect robot
  learning", "cross-paradigm robot policy comparison".
- **Inclusion criteria:** reports a reproducible success-rate metric on a
  named env/task, OR is a foundational statistical-methodology reference
  used by the contract (Wilson/bootstrap CI, MDE, paired tests), OR is a
  world-model / latent-MPC planning paper cited for the L3 comparison.
- **Exclusion criteria:** single-paper policy results with no released
  eval harness or reproducible protocol; simulation-only benchmarks with no
  LeRobot-compatible pretrained checkpoints (noted as related but out of
  direct-comparison scope).
- **Current state:** 25 entries in `paper/references.bib` already satisfy
  most of this retroactively. `lit-review-detail.md` should audit each
  against these criteria rather than assume they all still fit, and flag
  gaps (e.g., recent 2025-26 embodied-AI benchmark surveys not yet cited).
