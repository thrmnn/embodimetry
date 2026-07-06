---
status: draft
depends_on: [proposal]
---

# Lit review detail — embodimetry

> Executes `proposal.md`'s lit review method against the 25 entries already
> in `paper/references.bib`. Each entry keeps or sharpens a gap from the
> proposal, or it doesn't belong here — this pass audits fit, it doesn't just
> restate the bibliography.

## RQ1 — the contract (benchmarks & statistical rigor)

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `chi2023diffusion` (Diffusion Policy / PushT) | Source env + policy for the L0/L2 contract | No cross-paradigm comparison in the original work |
| `zhao2023learning` (ALOHA / ACT) | Source env + policy for L0/L1 | Same — single-paradigm evaluation |
| `liu2023libero` (LIBERO) | Source envs for SmolVLA L0 cells | Task suites, no shared multi-seed CI protocol across policies |
| `james2020rlbench`, `mees2022calvin` | Larger task taxonomies | No pretrained LeRobot-compatible checkpoints or shared protocol — cited as breadth without direct-comparison capability |
| `bohg2025open` (Open X-Embodiment) | Largest cross-embodiment dataset/taxonomy | Same gap — scale without a shared statistical contract |
| `henderson2018deep`, `agarwal2021deep` | Multi-seed/CI/statistical-rigor posture the contract adopts | These establish the *method* (bootstrap CI, multi-seed), not a benchmark — the paper's contribution is applying this posture cross-paradigm, which neither does |
| `brockman2016openai` (Gym) | Convention for floor baselines (no-op/random) on every env | — |
| `wilson1927probable`, `agresti1998approximate` | Wilson/Agresti-Coull interval — the CI method itself | Foundational, not a gap |
| `wilcoxon1945individual`, `mcnemar1947note`, `cohen1988statistical`, `efron1979bootstrap`, `efron1993introduction`, `bonferroni1936teoria` | Paired-comparison, effect-size, and multiple-comparison methodology | Foundational |
| `huggingfacehub2024` | Hub infra citation | — |

## RQ2 — the self-audit

No direct citation covers "an eval harness audits itself" as a contribution
— this appears to be a genuine gap rather than an omission. **Action for
Théo:** worth one more search pass (reproducibility-crisis / ML-testing
literature — e.g. work on silent bugs in RL benchmarks) to confirm this gap
is real and not just under-searched.

## RQ3 — world-model planning vs. learned policies

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `hafner2019planet` (PlaNet) | Foundational latent-dynamics planning | Benchmarked only against itself/RL baselines in its own envs |
| `zhou2024dinowm` (DINO-WM) | One of the two WM families in the L3 replication | Reports success on its own tasks; no shared protocol vs. a learned imitation policy |
| `assran2025vjepa2` (V-JEPA-2-AC) | Second WM family context (jepa-wms is the cross-repo comparison) | Same gap |

## RQ4 — fine-tuning and classical control

| Citation | Relevance | Gap it exposes |
|---|---|---|
| `black2024pi0` (Pi0), `shukor2025smolvla` (SmolVLA), `bu2025xvla` (XVLA) | Policy classes evaluated / deferred (pi-family, xvla to v1.1) | Each reports its own numbers; not cross-compared to classical or WM rungs under one contract |

## Coverage check against `proposal.md`'s target N

25/25 references audited above. **Gaps flagged for a follow-up search pass**
before locking:
1. RQ2's self-audit angle has no direct citation — confirm real gap or find one.
2. No 2025–26 embodied-AI benchmark *survey* paper is cited — worth checking
   for one that would strengthen the Related Work positioning.
3. `bohg2025open`'s year (2025) is worth double-checking against the actual
   Open X-Embodiment publication date/venue before submission.
