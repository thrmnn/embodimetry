---
status: review
depends_on: [proposal]
---

# Targets — venues and collaborators

> Runs in parallel with `lit-review-detail.md` and `results.md` — only needs
> `proposal.md`'s scope/RQs locked. Gates `draft` because the target venue's
> length/format/audience shapes how the draft gets written, not just where it
> gets submitted.
>
> **Passed a council review + one bulletproofing round** (2026-07-06). The
> venue table below was rewritten after a length check changed the picture
> materially — see the note.

**Length check, updated 2026-07-06:** the draft was 11pp when this file was
first written (not the "4pp" it originally assumed, inherited from stale
`proposal.md` framing). A same-day compression pass — cutting duplicated
restatements and fixing a LaTeX float-placement bug, zero content lost —
brought it to **9pp**. That changes the table below materially from the
previous "every page-capped venue is over budget" note: NeurIPS D&B's
~9pp+appendix cap is now in range on length alone (its scope-fit concern
stands regardless); CoRL's ~8pp still isn't.

## Candidate venues

| Venue | Scope fit | Fits at current length (9pp)? | Typical review time | OA/cost |
|---|---|---|---|---|
| arXiv (cs.RO primary, cs.LG secondary) | Exact fit — already the current target (`CITATION.cff`, README) | **Yes — no hard page limit** | Immediate (no review) | Free, fully OA |
| CoRL (Conference on Robot Learning) | Good fit for a paper that mixes a methodology contribution (RQ1/RQ2) with a genuine scientific finding (RQ3) — the venue explicitly welcomes both in one paper | No — typical 8pp cap; still needs ~1pp more compression, and the remaining cut would be substance not redundancy | ~4 months | Free |
| NeurIPS Datasets & Benchmarks track | Strong fit for RQ1/RQ2 alone (the contract + self-audit); **weaker fit for RQ3** — D&B reviewers score benchmark/dataset rigor and are prone to treating a scientific claim about planning capability (N=6/cell, one env per endpoint) as out-of-track scope creep, not a benchmark result | **Close — fits the ~9pp+appendix cap on length**, but expects heavier dataset-paper scaffolding (datasheet, reproducibility checklist, maintenance plan) than this draft currently has | ~3–4 months | Free |
| RSS (Robotics: Science and Systems) | Moderate fit — more systems/theory-leaning than benchmark papers historically | No — strict, competitive page limit | ~4 months | Free |
| ICRA / IROS | Moderate fit — broad robotics audience, less statistical-rigor-focused reviewing | No — 6–8pp | ~4–6 months | Free (registration cost) |

**Recommendation, revised this pass:** the earlier draft of this file
recommended NeurIPS D&B as primary. On reflection (and per the council's
pushback), that undersells the RQ3 finding's fit and oversells D&B's
tolerance for it — a scientific claim at N=6/cell reads as thin evidence to
a benchmark-rigor-focused reviewer pool. **arXiv-first stands regardless of
the length decision** (gates nothing, already in motion) — but this does
**not** resolve `proposal.md`'s blocking length item. The `draft` DAG node
stays blocked on Théo's compress-vs-accept call regardless of which venue
gets picked; arXiv having no page cap just means *that* venue isn't the
thing blocking it. For a conference
target, **CoRL is the better-argued primary choice** given the paper's
actual mixed nature — but only after Théo decides the length question in
`proposal.md`: either compress toward CoRL's ~8pp, or accept the longer
form and treat arXiv as the only venue for now, revisiting a conference
submission once (if) the paper is trimmed.

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

**Outreach note, revised this pass:** the L3 finding is a documented
negative for both DINO-WM and jepa-wms specifically on the contact task
(0/6 for both) — not a neutral mention, so "collegial heads-up" needs a
concrete purpose, not just a vague gesture. Standard practice is outreach
**after the arXiv posting exists**, not before anything is public — emailing
pre-post can read as seeking pre-approval rather than a courtesy notice,
and there's no public artifact yet to point to. Recommended plan: post to
arXiv first, then reach out with the specific arXiv link, framed as "here's
a direct comparison your model family appears in, wanted you to see it
before it circulates further" — a concrete, actionable ask (correct
anything they feel is mischaracterized) rather than an open-ended heads-up.
