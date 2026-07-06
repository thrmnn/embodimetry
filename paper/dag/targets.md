---
status: draft
depends_on: [proposal]
---

# Targets — venues and collaborators

> Runs in parallel with `lit-review-detail.md` and `results.md` — only needs
> `proposal.md`'s scope/RQs locked. Gates `draft` because the target venue's
> length/format/audience shapes how the draft gets written, not just where it
> gets submitted.

## Candidate venues

| Venue | Scope fit | Typical review time | OA/cost | Format constraint |
|---|---|---|---|---|
| arXiv (cs.RO primary, cs.LG secondary) | Exact fit — already the current target (`CITATION.cff`, README) | Immediate (no review) | Free, fully OA | No hard page limit; current draft targets 4pp body by convention |
| NeurIPS Datasets & Benchmarks track | Strong fit — the paper's core contribution is an eval contract/instrument, not a new policy | ~3–4 months | Free | Longer format (up to 9pp + appendix), benchmark-specific reviewer pool |
| CoRL (Conference on Robot Learning) | Good fit — robot-learning audience, receptive to benchmark/methodology papers | ~4 months | Free | 8pp typical |
| RSS (Robotics: Science and Systems) | Moderate fit — more systems/theory-leaning than benchmark papers historically | ~4 months | Free | Strict page limit, competitive |
| ICRA / IROS | Moderate fit — broad robotics audience, less statistical-rigor-focused reviewing | ~4–6 months | Free (registration cost) | 6–8pp |

**Recommendation to discuss:** arXiv-first (already in motion, gates nothing)
then NeurIPS D&B as the primary target given the paper's actual contribution
is the instrument + self-audit, which that track's reviewer pool is built to
evaluate — CoRL as the fallback/parallel submission.

## Potential collaborators / labs — needs Théo's input

This table is a template, not a filled map — I don't have reliable knowledge
of who's actively working adjacent to each RQ right now, and naming people
without that would be guessing, not research. Fill per RQ:

| RQ | Overlapping work / lab | Why (citation target / co-author / outreach) |
|---|---|---|
| RQ1 (the contract) | *(fill in)* | |
| RQ2 (self-audit) | *(fill in)* | |
| RQ3 (world-model planning) | *(fill in — likely DINO-WM / jepa-wms authors, given direct comparison)* | |
| RQ4 (fine-tuning/classical) | *(fill in)* | |

**Suggested starting point:** the authors behind `zhou2024dinowm` and
`assran2025vjepa2` are the most directly relevant given the L3 comparison
uses their model families — worth deciding whether to reach out pre-submission
(collegial heads-up) or let the paper stand alone at first submission.
