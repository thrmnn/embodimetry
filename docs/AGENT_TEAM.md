# Agent team & loops

**Version:** 1.0 · **Status:** living · **Scope:** Embodimetry

This repo is built by a multi-agent autonomous loop (Claude Code). Two docs
already cover the *plumbing*: [`ORCHESTRATION.md`](ORCHESTRATION.md) is the
wave mechanics (worktree isolation, disjoint file ownership, serial drain into
strict `main`), and [`ORCHESTRATION_PLAYBOOK.md`](ORCHESTRATION_PLAYBOOK.md)
is the catalog of named *workflows* (council, gpu-task, repro-audit,
prepublish-gate, …).

This doc is the missing third piece: **who is on the team** (the specialized
subagents and when to pick each) and **the three operating loops** that keep
the fleet moving (backlog autofix, sweep liveness, PR merge train). Read it to
re-run a loop from scratch; read the other two for the rules every agent obeys
while it runs.

---

## The agent roster

Each subagent owns a non-overlapping slice of the repo (the same partition the
wave mechanics enforce — see `ORCHESTRATION.md` → "File ownership mirrors
CODEOWNERS"). Pick the agent whose owned files the task lives in; if a task
spans two, it is two agents, not one boundary-crossing agent.

| Agent | Domain — files / tasks it owns |
|---|---|
| **bench-eval-engineer** | The core eval loop: `(policy, env, seed, n_eps) → CellResult`, env/policy registries, success thresholds, cell-boundary checkpointing. Owns `src/embodimetry/{eval,envs,policies,checkpointing}.py`. |
| **stats-rigor-reviewer** | Statistical claims — bootstrap/Wilson CIs, paired tests, effect sizes — in `src/embodimetry/stats.py`, the analysis notebook, and the writeup. **Veto authority** on any claim of significance. |
| **sweep-sre** | Everything operational: calibration spikes, long-sweep orchestration, OOM rescue, manifest provenance, HF Hub publishing. Owns `scripts/{calibrate,run_sweep,run_one,publish_results}.py` and the resume drill. |
| **render-pipeline-engineer** | The episode → MP4 render pipeline (`src/embodimetry/render.py`), thumbnails, ffmpeg/imageio encoding, and the size-cap policy that keeps Hub-dataset and Space-fetch latency in check. |
| **spaces-frontend-engineer** | The public Gradio Space (`space/app.py`, `space/requirements.txt`): leaderboard table, browse-rollouts UI, methodology tab, Hub-backed video playback on the free CPU tier. |
| **researcher-writeup** | The analysis notebook (`notebooks/01-write-finding.ipynb`), the 4-page arXiv LaTeX paper, and the failure-taxonomy labeling pass. The researcher voice — methods, results, discussion. **Defers to stats-rigor-reviewer on every numeric claim.** |
| **devx-toolsmith** | The boring infrastructure: `Makefile`, `.pre-commit-config.yaml`, CI workflows, release automation, dependabot, `RUNBOOK.md`, `MODEL_CARDS.md`, `CHANGELOG`, hook config. Keeps it boring. |
| **upstream-contributor** | The PR to `huggingface/lerobot` extracting our eval pipeline as a clean `lerobot.eval.multi_seed` module. Owns the fork, the PR, and review iteration. |

Generic agents fill the gaps:

- **Explore** — read-only fan-out search when you need a conclusion, not file
  dumps (locates code; does not review it).
- **Plan** — designs an implementation strategy / step plan before any edit.
- **general-purpose** — the catch-all for a multi-step task that fits no
  specialist above.

**Picking an agent:** start from the file the change lands in, not the verb.
"Make the sweep resumable" is `bench-eval-engineer` (checkpointing) *plus*
`sweep-sre` (the runner) — two owners, two agents. "Speed up the leaderboard"
is `spaces-frontend-engineer` if it is the Space, `render-pipeline-engineer` if
it is the video size cap. When unsure where a thing lives, send **Explore**
first, then dispatch the owner.

---

## The proven loops

Three loops are run repeatedly enough to be recipes. Each is **trigger →
steps → exit**. All repo-modifying steps run under `isolation: worktree` and
test via `PYTHONPATH=$(pwd)/src` — never `pip install -e .` in a worktree (the
editable `.pth` is static and rebinds the *parent's* `src/`).

### Loop 1 — Backlog discovery → verify → autofix → CI-gated merge

**Trigger:** start of an autonomous session, or any time the backlog of
small, safe fixes is unknown.

**Steps**
1. **Discover (parallel finders).** Fan out several read-only finders
   concurrently — lint/type debt, dead code, stale docs, flaky tests, TODO
   sweeps — each returning candidate items, not edits.
2. **Dedup.** Merge the finder outputs into one list; collapse duplicates and
   anything already covered by an open PR.
3. **Adversarially verify.** Hand each candidate to a second agent whose job
   is to *kill* it: is it real, is it safe to autofix unattended, does it cross
   an owner boundary or touch a guarded surface (see Guardrails)? Drop anything
   that is not unambiguously safe-to-autofix.
4. **Autofix, one worktree per item.** For each survivor, dispatch the owning
   agent (roster above) in its own worktree: branch (conventional-commit
   name) → make the fix → push → open a PR with a tight body (what + why +
   test evidence).
5. **CI-gated squash merge.** Let branch protection do the gating. `main` is
   strict (linear history, squash-merge, required up-to-date branch); required
   checks are **lint+format, mypy, pytest-fast**. Squash-merge each PR once
   green and up-to-date.

**Exit:** the deduped safe-to-autofix list is empty (or only owner-gated
items remain).

**Lesson — trust CI, not the local run.** A local `pytest -q` can pass while
the *same* check fails in CI (different runner, clean checkout, no static
editable `.pth`, stricter mypy resolution). The merge verdict is the **CI
check on the up-to-date branch**, never the agent's local green. If local and
CI disagree, CI is right — fix the cause, never `--no-verify` or force-push.

### Loop 2 — Long-sweep liveness + crash recovery

**Trigger:** an overnight (multi-hour, multi-night) GPU sweep is launched.

**Steps**
1. **Launch under a resume-on-crash runner.** A bash runner relaunches
   `run_sweep.py` with `--resume` (i.e. `make sweep-full SWEEP_NAME=…`) so a
   mid-cell death restarts that cell from episode 0 and **skips
   already-complete cells** — cell-boundary checkpointing makes this safe
   (`docs/RUNBOOK.md` → "Resume drill"). Wrap GPU work in `with_gpu_lock.sh` +
   `run_capped.sh --gpu-preflight`.
2. **Watch with a liveness Monitor.** Poll three independent signals, not one:
   - **parquet cell count** climbing (the only ground truth —
     `df.groupby(['policy','env','seed']).size()` on
     `results/<sweep>/results.parquet`);
   - the **sweep process** still present (`pgrep -f run_sweep.py`);
   - the **log mtime** still advancing (`results/<sweep>/sweep.log`).
   Stalled count + dead process + frozen log = crashed, not slow.

**The WSL2-restart failure mode.** A `wsl --shutdown` (the fix for a GPU-PV
desync — `docs/RUNBOOK.md` → "GPU health") wipes **everything at once**: the
sweep process, `/tmp` (so the GPU lock file is gone), and the GPU handshake.
The on-disk parquet survives; nothing else does.

**The recovery drill.**
1. Run `scripts/gpu_preflight.sh`; if it still fails, the desync is not
   cleared — do not relaunch.
2. Recreate the resume-on-crash runner (it died with the VM).
3. Relaunch the **same** sweep command with `--resume`; completed cells in the
   surviving parquet are skipped. If the restart picks up a stale half-written
   cell, drop that cell's rows from the parquet first (`docs/RUNBOOK.md`).

**Exit:** the parquet holds every planned cell-seed row (count == plan), the
sweep process has exited cleanly, and the GPU lock is released.

**Emphasize — the Monitor itself dies on WSL2 restart.** The liveness Monitor
is a process in the same VM; `wsl --shutdown` kills it too. So **every loop
wake must manually re-check liveness** — never assume the Monitor is still
watching. Re-run the three-signal check by hand at the top of each tick before
trusting that the sweep is alive.

### Loop 3 — PR watcher / merge train

**Trigger:** more than one PR is open against strict `main` (a wave's PRs are
draining).

**Steps**
1. **Scan all open PRs** for the repo (`gh pr list`), excluding owner-gated
   ones (see Guardrails).
2. **Classify each:**
   - **BEHIND** — branch is not up-to-date with `main` (strict protection
     blocks the merge). The watcher updates it: `gh pr update-branch`.
   - **BLOCKED** — a required check is failing. The watcher does **not** merge
     it; it flags the PR for the owning agent to fix the cause.
   - **READY** — up-to-date and green. Squash-merge it.
3. **After each merge, re-detect what landed.** Squash merges rewrite history,
   so `git branch --merged` misses them — use `gh pr list --state merged`. The
   merge that just landed makes every *other* open PR BEHIND again.
4. **Loop.** Re-scan; each PR you advance branches from / updates onto the
   **current** `origin/main`, never a stale base.

**Exit:** the open-PR queue is empty, or only BLOCKED / owner-gated PRs remain
(handed back for a fix or for the owner).

---

## Standing guardrails

Reusable operating rules the loops obey. These are **do NOT autonomously**
rules — each is a place where unattended action has a real blast radius, so the
agent stops and surfaces the item for the owner instead.

- **Do NOT push the upstream PR before user validation.** The
  `huggingface/lerobot` contribution is a reputation surface; the branch may be
  PR-ready locally, but pushing/opening it is owner-gated.
- **Do NOT create HF Hub repos** (datasets or Spaces). Hub-write steps —
  publishing the canonical parquet, creating a Space — are owner-driven; an
  agent prepares them and stops at the boundary.
- **Do NOT launch GPU jobs while a sweep runs.** The card is single-GPU behind
  a machine-global lock (`/tmp/embodimetry-gpu.lock`); a second CUDA dispatch
  races VRAM and can trigger the near-OOM WSL2 desync. One job at a time.
- **Do NOT edit cross-device surfaces.** `paper/main.tex`, `notebooks/`, and
  `paper/deck/` are authored on other devices; an autonomous edit here collides
  with out-of-band work. Treat them read-only in the loop and report wanted
  changes instead.
- **Keep the local `main` working tree pinned during a sweep.** A long sweep
  reads `src/` live; checking out a different ref or rebinding the editable
  install mid-run can poison in-flight cells. Do wave work in worktrees, leave
  the parent `main` tree untouched until the sweep exits.

When any rule fires, the agent does what it *can* do, then surfaces the gated
item in its report — it does not cross the boundary "just this once."

---

## Maintaining this doc

- Bump the **Version** header on any roster or loop change.
- A loop earns a place here only once it has been **run for real** — a recipe,
  not a plan. If it has not survived a session, it belongs in the planning
  notes, not this doc.
- Cross-references: this doc is the team + loops; `ORCHESTRATION.md` is the
  wave mechanics; `ORCHESTRATION_PLAYBOOK.md` is the workflow catalog. Keep the
  three from duplicating — link, don't restate.
