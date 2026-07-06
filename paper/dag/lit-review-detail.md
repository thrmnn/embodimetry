---
status: review
depends_on: [proposal]
---

# Lit review detail — embodimetry

> Executes `proposal.md`'s lit review method against the 25 entries already
> in `paper/references.bib`. Each entry keeps or sharpens a gap from the
> proposal, or it doesn't belong here — this pass audits fit, it doesn't just
> restate the bibliography.
>
> **Passed a council review + one bulletproofing round** (2026-07-06). One
> real bug found in `references.bib` itself and fixed — see RQ1 section.

## RQ1 — the contract (benchmarks & statistical rigor)

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `chi2023diffusion` (Diffusion Policy / PushT) | Source env + policy for the L0/L2 contract | No cross-paradigm comparison in the original work |
| `zhao2023learning` (ALOHA / ACT) | Source env + policy for L0/L1 | Same — single-paradigm evaluation |
| `liu2023libero` (LIBERO) | Source envs for SmolVLA L0 cells | Task suites, no shared multi-seed CI protocol across policies |
| `james2020rlbench`, `mees2022calvin` | Larger task taxonomies | No pretrained LeRobot-compatible checkpoints or shared protocol — cited as breadth without direct-comparison capability |
| `bohg2024open` (Open X-Embodiment) | Largest cross-embodiment dataset/taxonomy | Same gap — scale without a shared statistical contract |
| `henderson2018deep`, `agarwal2021deep` | Multi-seed/CI/statistical-rigor posture the contract adopts | These establish the *method* (bootstrap CI, multi-seed), not a benchmark — the paper's contribution is applying this posture cross-paradigm, which neither does |
| `brockman2016openai` (Gym) | Convention for floor baselines (no-op/random) on every env | — |
| `wilson1927probable`, `agresti1998approximate` | Wilson/Agresti-Coull interval — the CI method itself | Foundational, not a gap |
| `wilcoxon1945individual`, `mcnemar1947note`, `cohen1988statistical`, `efron1979bootstrap`, `efron1993introduction`, `bonferroni1936teoria` | Paired-comparison, effect-size, and multiple-comparison methodology | Foundational |
| `huggingfacehub2024` | Hub infra citation | — |

**Fixed this pass:** the citekey was `bohg2025open` but the entry's own
`year` field reads `{2024}` (ICRA proceedings year; the arXiv preprint
2310.08864 is from 2023) — a self-contradicting bibkey, not just a summary
typo. Renamed to `bohg2024open` in both `paper/references.bib` and the two
`\cite{}` sites in `paper/main.tex` (lines 169, 259).

## RQ2 — the self-audit

No direct citation covers "an eval harness audits itself" as a
contribution. The original draft of this file left this as a vague
"worth one more search pass" — sharpened with concrete starting points:
*"Deep Reinforcement Learning that Matters"* (Henderson et al., already
cited here for instability, not self-audit — check if it also touches
harness-bug detection), *"Empirical Design in Reinforcement Learning"*
(Patterson et al.), and the ML-testing-survey literature (e.g. work
surveyed under "Machine Learning Testing: Survey, Landscapes and
Horizons"). **Action for Théo:** run these three down before concluding the
gap is real rather than under-searched — this file's RQ2 gap claim in
`proposal.md` is currently hedged with "to our knowledge" precisely because
this hasn't been confirmed yet.

## RQ3 — the dynamics-complexity question (world-model planning vs. learned policies)

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `hafner2019planet` (PlaNet) | Foundational latent-dynamics planning | Benchmarked only against itself/RL baselines in its own envs |
| `zhou2024dinowm` (DINO-WM) | One of the two WM families in the L3 replication | Reports success on its own tasks; no shared multi-seed/CI protocol vs. a learned imitation policy |
| `assran2025vjepa2` (V-JEPA-2-AC) | Second WM family context (jepa-wms is the cross-repo comparison) | Same gap |

**Reworded this pass:** the gap statement previously said these papers are
"never benchmarked against a learned imitation policy," which overstates it
— DINO-WM's own paper includes some behavior-cloning-style baseline
comparisons internally. The defensible, and actually stronger, claim is
narrower: none of these three put their planner against imitation/
classical/fine-tuned policies under **one shared multi-seed, CI-bearing
statistical protocol spanning paradigms**. An isolated BC baseline inside a
single paper's own tables doesn't contradict that. `proposal.md`'s RQ3 gap
statement has been updated to match this exact phrasing.

## RQ4 — fine-tuning and classical control

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `black2024pi0` (Pi0), `shukor2025smolvla` (SmolVLA), `bu2025xvla` (XVLA) | Policy classes evaluated / deferred (pi-family, xvla to v1.1) | Each reports its own numbers; not cross-compared to classical or WM rungs under one contract |

## Coverage check against `proposal.md`'s target N

25/25 references audited above. **Open items before locking:**
1. RQ2's self-audit angle — run down the three named leads above before
   asserting the gap is real.
2. No 2025–26 embodied-AI benchmark *survey* paper is cited — worth checking
   for one that would strengthen the Related Work positioning.
3. Whether DINO-WM's own paper's internal BC baseline needs an explicit
   qualifying footnote in `main.tex` itself (not just here) — flagged in
   `proposal.md` as needing literature access beyond this repo.
