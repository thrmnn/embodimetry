# code_sha provenance audit — results/sweep-full/results.parquet (2026-07-06)

Static, read-only audit answering one question: does `results/sweep-full/results.parquet`
spanning 13 distinct `code_sha` values (the publish preflight's provenance guard,
`scripts/publish_results.py::_provenance_integrity_error`, correctly aborts on this)
represent a *real* reproducibility problem, or a cosmetic one?

**Scope.** This audit does not modify the guard, the parquet, or any code. It is
evidence for a decision the guard's error message defers to a human: "re-run the
affected cells at one HEAD, or split the publish per code_sha, before publishing."
That decision is not made here — see Bottom line.

## What we used

`git rev-parse <sha>:src/embodimetry` at each of the 13 shas the parquet contains,
to get the actual runtime-package tree hash independent of unrelated commits (docs,
dashboard, chore) that bump the git SHA without changing `src/embodimetry/`. Then,
for any pair of shas within one cell that had *different* tree hashes, `git diff`
between those two trees plus direct reading of the changed source to determine
whether that specific cell's policy executes the changed code path at all.

## Finding 1 — 13 git shas collapse to 3 actual runtime states

| Tree hash | Commits sharing it | What changed to get here |
|---|---|---|
| `a4c675dd` | `7361d962` (the ACT normalization fix, PR #51), `fa6f9ac7`, `e1dd0adc`, `f05285ef`, `00d188e0`, `5a8a79c9`, `0a8655df` | Only `7361d962` touches `src/embodimetry/`; the other 6 are docs/security-audit/paper-prose commits with zero `src/` diff |
| `4f74b9d8` | `a581b971`, `ae6002b7`, `fcb08552`, `d9cdb28a` | Dashboard-only changes (science panels), a new `make reproduce` script, a shell-script tracking chore — none touch `eval.py` or policy loading |
| `185c9239` | `38ae2cbf` (2026-05-12, the one chronological outlier) | Predates the other two states; see Finding 2 for why its one real diff is inert |

## Finding 2 — the two genuine cross-tree diffs don't touch the affected policy's code path

Two cells mix rows across the *different* tree hashes above (not just different git
shas with identical trees):

- **`random` × `libero_spatial`** (200 rows @ `4f74b9d8`, 50 rows @ `a4c675dd`). The
  only file differing between these trees is `eval.py`, and the diff is exactly the
  ACT legacy-normalization fix (PR #51) — it only changes
  `_recover_dataset_stats_from_safetensors` / `_load_pretrained_policy`, which are
  reached exclusively from the *pretrained-checkpoint* loading branch. `random` and
  `no_op` are `is_baseline=True` policies that take a separate branch in `eval.py`
  (`if spec.is_baseline: ... if spec.name == "no_op": ... if spec.name == "random":`)
  and never call the changed functions. **The fix is inert for this cell.**
- **`diffusion_policy` × `pusht`** (75 + 25 rows @ `4f74b9d8`, 25 rows @ `185c9239`).
  The only file differing is `policies.py`, and the diff adds two new *optional*
  schema fields (`paper_reported_success`, `paper_reported_notes`) for an unrelated
  Space dashboard panel — purely additive, defaults to `None`/absent. Confirmed
  separately: `configs/policies.yaml`'s `diffusion_policy` entry (`repo_id`,
  `revision_sha` — the fields that actually determine what checkpoint gets loaded)
  has **zero diff** between these two commits. **The fix is inert for this cell.**

## Finding 3 — the ACT×aloha cell itself is clean

`act` × `aloha_transfer_cube` (200 rows @ `7361d962`, 50 rows @ `fa6f9ac7`) both share
tree `a4c675dd` — `7361d962` is the fix itself, `fa6f9ac7` (26 minutes later, docs-only)
changes nothing further. All 250 episodes ran under the identical, post-fix
normalization logic that produces the published **0.824** headline.

## Bottom line

All 7 mixed-`code_sha` cells, and by extension all 22 cells in the parquet, are
verified **behaviorally reproducible from a single effective codebase state** —
the guard's literal "count of distinct git shas" is a stricter proxy than the actual
invariant it's protecting (per-policy runtime-code identity), and in this specific,
fully-audited case the stricter proxy produces a false positive.

This does **not** mean the guard should be relaxed, in general or via a
special-cased exception — see the discussion in `paper/dag/` review notes: a
permanent allowlist for one verified-safe historical case is an attractive
nuisance that erodes the guard's unconditional value for every future publish.
The recommended path is a **one-time, explicit, out-of-band decision by the
project owner** — this document is the evidence for that decision, not the
decision itself. Options, in order of how much they touch the codebase:
1. Manually author the publish with a documented, visible break-glass step
   (not a silent code path) referencing this audit.
2. Re-run just the 2 genuinely-mixed cells (`random`×`libero_spatial`,
   `diffusion_policy`×`pusht`) at current `HEAD` for a parquet that passes the
   guard with zero exceptions — cheap relative to the full 110-cell sweep,
   and removes the need for any judgment call at publish time.
3. Leave the guard and parquet as-is and hold the publish until (2) happens
   anyway, since it's the option that requires no waiver of any kind.
