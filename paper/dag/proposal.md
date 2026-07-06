---
status: review
depends_on: []
---

# Proposal — embodimetry

> Reconstructed from the existing `paper/main.tex` (abstract + intro + related
> work), not written from a blank page — a full draft already exists. This is
> the retroactive DAG entry point: review it first, since `results.md`,
> `figures.md`, `lit-review-detail.md`, and `targets.md` all depend on the RQs
> and gaps locked here matching what the draft actually argues.
>
> **Passed a council review + one bulletproofing round** (2026-07-06). Fixes
> applied below; two items are flagged as genuinely needing Théo's call, not
> something more review resolves.

## Working title

*embodimetry: a Capability-Ladder Audit — measuring pretrained, fine-tuned,
and classical robot policies on one reproducible eval contract*

**Open question for review:** the title names pretrained/fine-tuned/classical
but not the world-model rung (L3), even though the abstract's third
contribution — the nav-vs-contact replication — is a headline result. Worth
deciding whether the title should name L3 explicitly or stays paradigm-neutral
on purpose (the ladder framing already implies "and beyond").

**Blocking open item — length/venue, found during bulletproofing:** the
"4pp" framing below and in `targets.md` is stale. Rebuilding `paper/main.tex`
from its current source (982 lines, `make -C paper`) produces an **11-page**
PDF with no LaTeX errors — not 4. The draft hit 4pp once, at the last
compression pass (commit `da6c594`, 2026-05-26, 444 lines); it has since
roughly doubled through real feature work (L3 section, capability-ladder
framing, the ACT ablation table, failure taxonomy) with no compression pass
since. `paper/main.pdf` itself is gitignored by design (`paper/.gitignore` —
arXiv builds the PDF from `.tex`/`.bib`/figures directly, so it's never
committed); the local copy on disk was simply a stale local build from the
old, shorter source and has been rebuilt to match current `main.tex` as part
of this pass. So the "4pp" claim wasn't just aspirational drift in this
proposal — the actual page count had genuinely moved and nothing surfaced
it, since there's no committed PDF for anyone to notice was wrong.
**This needs Théo's call**: compress back toward a conference length,
or accept ~11pp and target arXiv + a venue that allows it. See `targets.md`
for the venue-fit consequences.

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
4. **RQ4 (secondary — the middle rungs, spine-supporting by design).** Under
   the same MDE-bounded contract, where does continued fine-tuning (L1) or a
   competent classical controller (L2) move the needle relative to a strong
   pretrained baseline? Unlike RQ1–RQ3, no RQ4 finding is expected to land as
   a MAIN result (see `results.md`) — its evidence is spine-supporting
   (kept in the main ladder table, per `main.tex`'s own framing) but not one
   of the paper's three headline contributions. Said explicitly here so a
   reviewer doesn't ask why a numbered RQ produces no headline finding.

**Note on falsifiability (council finding):** RQ1 and RQ2 are answered by
demonstration/construction (build the contract; catch a real bug) rather than
by a hypothesis that could come out either way. That's an accurate
description of what this paper does, not a defect to fix — but it's worth
being explicit in the intro that RQ1/RQ2 are design objectives demonstrated
by the instrument, while RQ3/RQ4 are genuinely empirical (could have come out
differently, and RQ4 in fact did — the L1 lift is null).

## The gap each RQ addresses

- **RQ1 gap:** `main.tex`'s own Related Work (§Robot-learning benchmarks and
  statistical rigor) is more precise than an earlier draft of this file was:
  it names PushT, the Aloha suite, and LIBERO as the de facto references,
  and RLBench/CALVIN/Open X-Embodiment as offering "larger taxonomies but no
  pretrained LeRobot-compatible checkpoints or shared protocol." None ship a
  multi-policy leaderboard with shared seed accounting, multi-seed CIs, and
  re-runnable rows across paradigms. This proposal now inherits that
  precision rather than restating it more broadly.
- **RQ2 gap:** No neighboring benchmark treats its own harness as an audit
  target, *to our knowledge* — this claim currently has **no supporting
  citation** in `main.tex`'s Related Work (verified: the section's two
  paragraphs cover RQ1 and RQ3's gaps only). Either add a Related Work
  sentence addressing this before submission, or keep it hedged as
  unverified rather than asserted. See `lit-review-detail.md` for concrete
  search leads.
- **RQ3 gap:** World-model planners (PlaNet, DINO-WM, V-JEPA-2-AC) report
  success only on their own tasks, never under **one shared multi-seed,
  CI-bearing statistical protocol spanning paradigms** — narrower and more
  defensible than "never against a learned imitation policy" (DINO-WM's own
  paper includes some
  behavior-cloning baselines internally; the real gap is the shared
  multi-seed/CI protocol, not the mere existence of any imitation baseline
  anywhere). So "when does planning substitute for learning" has never been
  measured on a ruler that also holds a policy baseline under matched
  statistics.
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
- **Target N / stopping rule:** aim for 25–35 entries; stop adding once two
  consecutive keyword-search passes surface no citation that sharpens an
  RQ's gap statement or gets cut per the exclusion criteria (saturation, not
  a fixed count).
- **Current state:** 25 entries in `paper/references.bib`, audited against
  these criteria in `lit-review-detail.md`. One citekey/year mismatch found
  and fixed (`bohg2025open` → `bohg2024open`, matching the entry's own
  `year=2024` field). Open item: confirm the RQ2 gap via the search leads in
  `lit-review-detail.md` before this locks — a real gap search, not just an
  absence-of-citation assumption. Also open: whether DINO-WM's own paper
  includes an imitation-learning baseline comparison that would need
  qualifying language in the RQ3 gap statement (needs literature access
  beyond what's verifiable from this repo).
