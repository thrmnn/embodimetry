# Ship-Readiness Scorecard & Roadmap

> **Living doc.** This is the single source of truth for "are we ready to ship, and
> what's left." It is maintained by the autonomous loop: re-score when a track lands,
> tick objectives as their acceptance specs are met. Each dimension has an explicit
> 0–10 rubric and current evidence so the score is auditable, not vibes.

**Last updated:** 2026-06-14 · **Primary ship goal:** v1 public launch (GA)
**Headline:** **v1 public-ship readiness ≈ 6.5 / 10** — engineering is strong (8–9);
the gap is the *publish/launch* actions, most of which are user-gated (create the Hub
dataset + Space, post the paper). Nothing engineering-side blocks the launch.

---

## How to read this

- **Score** is 0–10 against the rubric in each row.
- **Composite** is the weighted mean over the v1-ship dimensions (weights below). The
  v1.1 expansion is a *roadmap milestone*, not a v1 GA gate, so it is scored separately
  and excluded from the headline.
- **Gate** = does this block v1 GA? **Owner** = who must act (user-gated items cannot be
  done autonomously).

---

## v1 public-ship dimensions

| # | Dimension | Score | Wt | Gate? | Evidence (2026-06-14) | Gap to 10 |
|---|-----------|:----:|:--:|:----:|------------------------|-----------|
| 1 | Code quality & CI | 9 | 13 | no | 7 workflows; ruff + mypy (strict); branch protection requires lint/mypy/pytest; schema-drift + publish-provenance guards (#203) | space-smoke not a required check; a few env-dependent tests flake locally |
| 2 | Test coverage | 8 | 11 | no | 758 tests; 86% measured vs 82% floor | floor is modest; gpu/sim paths excluded from CI |
| 3 | Reproducibility | 9 | 14 | no | pinned `lerobot==0.5.1`; policy checkpoint SHAs; deterministic seed contract; cell-boundary checkpointing; config-aware coverage gate (#201) | manifest `started_utc`/`eval_run_id` lost across `--resume` (#12); no reward columns (#6) |
| 4 | Documentation | 7 | 13 | soft | comprehensive `docs/`; README user/dev split in flight (#206); dev hub added | v1.1 dataset card (#11) pending; audit docs under-cross-linked |
| 5 | **Public dataset (v1)** | 4 | 17 | **YES** | corrected v1.0.2 parquet prepared (4375 rows / 90 cells); `publish_results.py --dry-run` green | **`thrmnn/embodimetry-v1` returns 401 publicly** — Hub repo create + upload are user-gated |
| 6 | **Public dashboard (Space)** | 3 | 15 | **YES** | app boot-tested; schema-drift guarded; pooled-LIBERO view (#177) in flight | **Space returns 401 publicly** — create + subtree-push user-gated |
| 7 | Paper / dissemination | 6 | 10 | **YES** | 4-page draft; figures embedded; L3 un-gated to a qualified result; comms plan exists | arXiv ID `TBD`; not posted; launch sequence not triggered |
| 8 | Licensing / legal | 8 | 7 | no | MIT; `CITATION.cff` present | CITATION version lags (`1.0.0` vs code `1.0.2`); Gemma-license review deferred to pi0 (v1.1+) |

**Weighted composite:** 9·.13 + 8·.11 + 9·.14 + 7·.13 + 4·.17 + 3·.15 + 6·.10 + 8·.07
= **6.5 / 10**.

The three GA gates (5, 6, 7) are the score's anchor and are all primarily **user-gated**:
the codebase is launch-ready; the dataset, Space, and paper just have to be *published*.

---

## v1.1 expansion (next milestone — not a v1 GA gate)

| Dimension | Score | Evidence | Gap |
|-----------|:----:|----------|-----|
| v1.1 sweep | 3 | 10-task per-suite LIBERO sweep running (~50/200 cells; single `code_sha`) | finish 200/200 (#1) |
| v1.1 figures | 6 | `replication_scatter` per-task pooling **code done** (#205) | regenerate from full sweep data (#10) |
| v1.1 publish | 1 | versioning decided: new repo `embodimetry-v1.1`, v1 immutable (#9) | card (#11) + Hub repo + upload |

---

## Roadmap to GA — objective specifications

Each objective has an **acceptance spec** (the observable condition that closes it).
Checkboxes are ticked by the loop when the spec is verified.

### v1 public launch (GA)

- [ ] **O1 — Publish v1 dataset.** *Spec:* `curl -s https://huggingface.co/api/datasets/thrmnn/embodimetry-v1` → `200`; `results.parquet` present with 90 cells / 4375 rows; schema-drift CI green against the live URL. *Owner:* **user** (`hf repo create`) + loop (upload script ready). *Blocked on user.*
- [ ] **O2 — Deploy Space.** *Spec:* `curl … /api/spaces/thrmnn/embodimetry` → `200`; app boots on free tier; leaderboard renders the live parquet. *Owner:* **user** (create + subtree push) + loop. *Dep:* O1.
- [ ] **O3 — Docs GA-ready.** *Spec:* #206 merged; dashboard badge flips `deploying → live` once O2; dataset card current. *Status:* #206 in flight (auto-merge armed).
- [ ] **O4 — Paper posted.** *Spec:* arXiv ID assigned; final figures; preprint live; `CITATION.cff` + README badge updated with the ID. *Owner:* **user.**
- [ ] **O5 — Tag v1.0.2 release.** *Spec:* version triple (`VERSION` / `__version__` / `pyproject`) all `1.0.2` (✓); tag pushed; `release.yml` builds + attaches artifacts. *Owner:* **user.**
- [ ] **O6 — Bump CITATION to 1.0.2.** *Spec:* `CITATION.cff` `version: 1.0.2`, date-released current. *Owner:* loop (small PR). *Unblocked.*

### v1.1 expansion (post- or parallel-to-GA)

- [ ] **M1 — v1.1 sweep complete.** *Spec:* parquet groupby `(policy,env,seed)` = 200; single `code_sha`; manifest `finished_utc` set. *Status:* in progress (#1).
- [ ] **M2 — v1.1 figures regenerated.** *Spec:* `replication_scatter` shows 4 pooled 10-task LIBERO points (annotated `10-task pooled`). *Dep:* M1 (#10).
- [ ] **M3 — v1.1 dataset card + repo.** *Spec:* `docs/HUB_DATASET_README.md` describes v1.1; `embodimetry-v1.1` published. *Dep:* M1 + user Hub create (#11).
- [ ] **M4 — Space v1.1 view.** *Spec:* pooled-LIBERO leaderboard live (#177 merged + requirements pin bumped). *Dep:* #177.
- [ ] **M5 — Pipeline hygiene.** manifest preservation (#12), reward columns (#6), n-aware MDE band (#13).

---

## Maintenance protocol

1. On any track landing, update the relevant **Score** + **Evidence**, recompute the
   composite, and tick any newly-satisfied objective spec.
2. Keep **GA gates (O1–O5)** front-and-center — they are mostly user-gated, so surface
   them whenever the user checks in.
3. When the headline crosses **8.0**, the remaining gap should be only user actions
   (publish + post); flag that the project is one user-session from launch.
