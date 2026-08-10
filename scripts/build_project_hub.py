"""Builds the embodimetry cockpit: the orchestration hub grown into a tailnet
PWA. One page ties together every surface (dashboard, Space, site, deck, paper,
docs) plus glance panes: status strip with an always-visible build-age chip,
fleet/needs-Théo panes hydrated from `_hub/fleet_status.json`, sweep progress,
headline results, and upstream-PR state. Pure static output — never edit
`_hub/**.html` by hand, edit this script and re-run it.

    python scripts/build_project_hub.py

The complete deployable tree is assembled under `_hub/_stage/` (single owner:
the service-worker precache list is derived by walking what this script wrote).
Nothing is ever emitted outside gitignored `_hub/`. Deploy with
`scripts/push_cockpit.sh`; serve the stage root for a local smoke test:

    python -m http.server 8888 -d _hub/_stage
    # cockpit: http://127.0.0.1:8888/_hub/
"""

from __future__ import annotations

import html
import json
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import yaml

import hubkit as hk

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "_hub"
STAGE = OUT / "_stage"
DOCS_OUT = OUT / "docs"
GENERATOR = "scripts/build_project_hub.py"
# The tablet's own 127.0.0.1 is not the laptop; only the tailnet IP works there.
DASHBOARD_URL = "http://100.104.205.62:7860"

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)
_SYM = {
    "idle": "·",
    "running": "▶",
    "blocked": "■",
    "awaiting-theo": "✋",
    "done": "✓",
    "failed": "✗",
}
_e = html.escape

# academic-paper-workflow DAG order + upstream deps (mirrors each artifact's
# own `depends_on` header -- duplicated here only as a fallback default for
# artifacts missing a header, not as the source of truth).
_PAPER_DAG_NODES = [
    ("proposal", "paper/dag/proposal.md", []),
    ("results", "paper/dag/results.md", ["proposal"]),
    ("figures", "paper/dag/figures.md", ["results"]),
    ("lit-review-detail", "paper/dag/lit-review-detail.md", ["proposal"]),
    ("targets", "paper/dag/targets.md", ["proposal"]),
]


def _git(*args: str) -> str:
    try:
        return (
            subprocess.check_output(["git", *args], cwd=REPO, stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        return ""


def _crumb() -> str:
    return hk.breadcrumb([("embodimetry hub", "../index.html"), ("doc", None)])


def _frontmatter(md_path: Path) -> dict:
    m = _FRONTMATTER.match(md_path.read_text())
    if not m:
        return {}
    data = yaml.safe_load(m.group(1))
    return data if isinstance(data, dict) else {}


def _read_fleet() -> dict | None:
    path = OUT / "fleet_status.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def render_docs() -> dict[str, str]:
    """Render reference docs to standalone HTML pages; return name -> relative href."""
    DOCS_OUT.mkdir(parents=True, exist_ok=True)
    prov = hk.git_provenance(REPO, GENERATOR)
    targets = {
        "ship-readiness": REPO / "docs/SHIP_READINESS.md",
        "runbook": REPO / "docs/RUNBOOK.md",
        "publish-runbook": REPO / "docs/PUBLISH_RUNBOOK.md",
        "pipeline-roadmap": REPO / "docs/PIPELINE_ROADMAP.md",
        "architecture": REPO / "docs/ARCHITECTURE.md",
        "design": REPO / "docs/DESIGN.md",
        "sweep-v11-results": REPO / "docs/SWEEP_V11_LIBERO_RESULTS.md",
        "changelog": REPO / "CHANGELOG.md",
    }
    hrefs = {}
    for slug, md_path in targets.items():
        if not md_path.exists():
            continue
        out_path = DOCS_OUT / f"{slug}.html"
        # Every rendered doc lands at _hub/docs/{slug}.html regardless of the
        # source's own location, so the climb back to repo root is always two
        # levels — the source-location branch here was dead code (ruff RUF034).
        base = "../.."
        hk.render_doc_page(md_path, out_path, crumb=_crumb(), provenance=prov, base=base)
        hrefs[slug] = f"docs/{slug}.html"
    return hrefs


def render_paper_dag() -> tuple[str, dict[str, str]]:
    """Render the academic-paper-workflow DAG: status badges + rendered pages.

    A node is BLOCKED if any dependency isn't `locked` yet, regardless of its
    own status -- this is the DAG's whole point (don't let draft/results drift
    ahead of an unlocked proposal).
    """
    prov = hk.git_provenance(REPO, GENERATOR)
    statuses: dict[str, str] = {}
    cards = []
    for slug, rel_path, deps in _PAPER_DAG_NODES:
        md_path = REPO / rel_path
        if not md_path.exists():
            continue
        fm = _frontmatter(md_path)
        status = fm.get("status", "draft")
        deps = fm.get("depends_on", deps)
        statuses[slug] = status
        blocked = any(statuses.get(d, "draft") != "locked" for d in deps)
        kind = {"locked": "ok", "review": "info"}.get(status, "amber")
        if blocked and status not in ("locked",):
            kind = "warn"
        out_path = DOCS_OUT / f"paper-{slug}.html"
        hk.render_doc_page(md_path, out_path, crumb=_crumb(), provenance=prov, base="../..")
        dep_note = f"depends on: {', '.join(deps)}" if deps else "depends on: none"
        state_note = f"{status.upper()}" + (" — blocked on deps" if blocked else "")
        cards.append(
            hk.card(
                slug.replace("-", " ").title(),
                dep_note,
                f"docs/paper-{slug}.html",
                kind=kind,
                meta=state_note,
            )
        )

    draft_deps_locked = all(
        statuses.get(n) == "locked" for n in ("results", "figures", "lit-review-detail", "targets")
    )
    draft_exists = (REPO / "paper/main.pdf").exists()
    cards.append(
        hk.card(
            "Draft (paper/main.pdf)",
            "Assembled from results + figures + lit-review-detail + targets once "
            "all four are locked."
            + (
                ""
                if draft_deps_locked
                else " Draft currently exists AHEAD of formal DAG approval — "
                "predates this workflow; treat upstream artifacts as a "
                "retroactive review pass, not a block on the existing PDF."
            ),
            "../paper/main.pdf",
            kind="ok" if draft_exists else "warn",
            meta="paper/main.tex",
        )
    )
    return hk.section("Paper DAG (academic-paper-workflow)", cards, anchor="paper-dag"), statuses


def _ship_score() -> str:
    md = (REPO / "docs/SHIP_READINESS.md").read_text()
    m = re.search(r"readiness ≈ ([\d.]+) / 10", md)
    return m.group(1) if m else "?"


def _sweep_summaries() -> list[dict]:
    out = []
    manifests = sorted(REPO.glob("results/*/sweep_manifest.json")) + sorted(
        REPO.glob("results/probes/*/sweep_manifest.json")
    )
    for mf in manifests:
        try:
            d = json.loads(mf.read_text())
        except Exception:
            continue
        cells = d.get("cells", [])
        done = sum(1 for c in cells if c.get("status") == "completed")
        failed = sum(1 for c in cells if c.get("status") not in (None, "pending", "completed"))
        out.append(
            {
                "name": mf.parent.name,
                "completed": done,
                "total": len(cells),
                "failed": failed,
                "started_utc": d.get("started_utc"),
                "finished_utc": d.get("finished_utc"),
                "active": not d.get("finished_utc"),
            }
        )
    return out


def render_strip(built_at: str, fleet: dict | None, dag: dict[str, str], prs: list[dict]) -> str:
    locked = sum(1 for s in dag.values() if s == "locked")
    chips = [
        f'<span class="chip dim" id="chip-build" data-ts="{built_at}" data-pre="build ">'
        f"build {built_at}</span>"
    ]
    if fleet and fleet.get("generated_at"):
        ts = _e(fleet["generated_at"])
        up = "up" if fleet.get("dashboard_up") else "down"
        chips += [
            f'<span class="chip dim" id="chip-fleet" data-ts="{ts}" data-pre="fleet ">'
            f"fleet {ts}</span>",
            f'<span class="chip dim" id="chip-dash" data-ts="{ts}" '
            f'data-pre="dashboard {up} · seen ">dashboard {up}</span>',
        ]
    else:
        chips += [
            '<span class="chip dim" id="chip-fleet">fleet —</span>',
            '<span class="chip dim" id="chip-dash">dashboard —</span>',
        ]
    pr_txt = " · ".join(f"#{p.get('number')} {p.get('state', '?')}" for p in prs) or "PRs —"
    chips.append(f'<span class="chip" id="chip-pr">{_e(pr_txt)}</span>')
    dag_kind = "fresh" if locked == 5 else ""
    chips.append(f'<span class="chip {dag_kind}">DAG {locked}/5 locked</span>')
    chips.append(f'<span class="chip">ship {_e(_ship_score())}/10</span>')
    chips.append('<button id="btn-refresh" class="chip btn" type="button">↻ refresh</button>')
    dag_chips = "".join(
        f'<a class="chip dagc" href="docs/paper-{slug}.html">'
        f"{ {'locked': '✓', 'review': '◐'}.get(status, '○') } {slug}</a>"
        for slug, status in dag.items()
    )
    return (
        '<div id="banner" class="banner" hidden></div>'
        f'<div class="strip">{"".join(chips)}</div>'
        f'<div class="strip dagrow">{dag_chips}</div>'
    )


def render_needs_theo(fleet: dict | None) -> str:
    items = (fleet or {}).get("needs_theo", [])
    rows = "".join(
        f'<div class="need"><strong>{_e(n.get("track", ""))}</strong> — {_e(n.get("ask", ""))} '
        f'<span class="mut">since {_e(n.get("since", ""))} '
        f'(<span data-ts="{_e(n.get("since", ""))}" data-pre="as of "></span>)</span></div>'
        for n in items
    )
    hidden = "" if items else " hidden"
    return f'<div id="needs-theo" class="needs"{hidden}><h2>Needs Théo</h2>{rows}</div>'


def render_fleet_pane(fleet: dict | None) -> str:
    # Baked no-JS fallback carries track id/state/now only — gate evidence and
    # milestones are client-hydrated so they never ride inside precached HTML.
    if not fleet:
        inner = '<p class="mut">no fleet_status.json yet — orchestrator has not reported.</p>'
    else:
        rows = [
            f'<div class="trk"><span class="st {_e(t.get("state", "idle"))}">'
            f"{_SYM.get(t.get('state', 'idle'), '·')} {_e(t.get('state', 'idle'))}</span> "
            f"<strong>{_e(t.get('id', ''))}</strong> "
            f'<span class="mut">{_e(t.get("now", ""))}</span></div>'
            for t in fleet.get("tracks", [])
        ]
        inner = "".join(rows)
    return f'<section id="fleet"><h2>Fleet</h2><div id="fleet-pane">{inner}</div></section>'


def render_sweep_pane(fleet: dict | None) -> str:
    sweeps = _sweep_summaries()
    active = [s for s in sweeps if s["active"]]
    if active:
        s = active[0]
        pct = 100 * s["completed"] / max(s["total"], 1)
        if s["started_utc"] and s["completed"]:
            elapsed_h = (
                datetime.now(UTC) - datetime.fromisoformat(s["started_utc"])
            ).total_seconds() / 3600
            rate = s["completed"] / max(elapsed_h, 1e-9)
            eta = f"ETA ≈ {(s['total'] - s['completed']) / rate:.1f} h"
        else:
            eta = "pace — (started_utc lost across --resume, #12)"
        inner = (
            f"<strong>{_e(s['name'])}</strong>"
            f'<div class="bar"><div style="width:{pct:.1f}%"></div></div>'
            f"{s['completed']}/{s['total']} cells · {s['failed']} failed · {_e(eta)}"
        )
    else:
        done = [s for s in sweeps if s["finished_utc"]]
        if done:
            last = max(done, key=lambda s: s["finished_utc"])
            inner = (
                f"no active sweep · last: <strong>{_e(last['name'])}</strong> "
                f"{last['completed']}/{last['total']}"
                + (f" · {last['failed']} failed" if last["failed"] else "")
                + f" · finished {_e(last['finished_utc'][:10])}"
            )
        else:
            inner = "no sweep manifests found"
    orch = ""
    for s in (fleet or {}).get("sweeps", []):
        head = f" — {_e(s['headline'])}" if s.get("headline") else ""
        orch += f"{_e(s.get('name', ''))} {s.get('completed', '?')}/{s.get('total', '?')}{head}"
    return (
        f'<section id="sweep"><h2>Sweep</h2><p>{inner}</p>'
        f'<div id="sweep-orch" class="mut">{orch}</div></section>'
    )


def render_results_pane(docs: dict[str, str]) -> str:
    md_path = REPO / "docs/SWEEP_V11_LIBERO_RESULTS.md"
    if not md_path.exists():
        return ""
    md = md_path.read_text()
    m = re.search(r"\*\*Headline verdict:\s*(.*?)\*\*", md, re.DOTALL)
    verdict = re.sub(r"\s+", " ", m.group(1)).strip() if m else ""
    sec = re.search(r"\n## 1\.[^\n]*\n(.*?)(?=\n## )", md, re.DOTALL)

    def clean(cell: str) -> str:
        return re.sub(r"\s*\[[^\]]*\]", "", cell.replace("**", "")).strip()

    rows = ""
    for ln in (sec.group(1) if sec else "").splitlines():
        if ln.startswith("| libero"):
            cells = [clean(c) for c in ln.strip().strip("|").split("|")[:4]]
            rows += "<tr>" + "".join(f"<td>{_e(c)}</td>" for c in cells) + "</tr>"
    table = (
        '<table class="mini"><thead><tr><th>Suite</th><th>Published</th>'
        f"<th>v1.1 suite-avg</th><th>Gap</th></tr></thead><tbody>{rows}</tbody></table>"
        if rows
        else ""
    )
    link = docs.get("sweep-v11-results", "#")
    return (
        f'<section id="results"><h2>Headline results</h2><p>{_e(verdict)}</p>{table}'
        f'<p class="mut">numbers quoted from the reviewed doc, never the parquet — '
        f'<a href="{link}">full analysis</a></p></section>'
    )


def render_pr_pane(fleet: dict | None) -> tuple[str, list[dict]]:
    prs = []
    rows = ""
    for t in (fleet or {}).get("tracks", []):
        pr = t.get("pr")
        if not pr:
            continue
        prs.append(pr)
        repo = pr.get("repo", "thrmnn/embodimetry")
        rows += (
            f'<div class="pr" data-repo="{_e(repo)}" data-num="{pr.get("number")}">'
            f'<span class="mut">{_e(t.get("id", ""))}</span> <span class="prx">'
            f'<span class="pill info">#{pr.get("number")} {_e(pr.get("state", "?"))}</span> '
            f"{_e(pr.get('title', ''))} "
            f'<span class="mut">checked <span data-ts="{_e(pr.get("checked_at", ""))}"></span>'
            f"</span></span></div>"
        )
    if not rows:
        rows = '<p class="mut">no tracked PRs in fleet_status.json.</p>'
    commits = "".join(
        f"<li><code>{_e(ln.split(' ', 1)[0])}</code> {_e(ln.split(' ', 1)[1])}</li>"
        for ln in _git("log", "--pretty=%h %s", "-8").splitlines()
        if " " in ln
    )
    return (
        f'<section id="prs"><h2>Upstream PRs &amp; activity</h2><div id="pr-pane">{rows}</div>'
        f'<h3 class="mut">recent commits (at build)</h3><ul class="ms">{commits}</ul></section>',
        prs,
    )


def render_linkrow(fleet: dict | None) -> str:
    return (
        '<div class="linkrow">'
        '<a href="../paper/deck/index.html">deck</a> · '
        '<a href="../site/index.html">site</a> · '
        '<a href="../paper/main.pdf">paper PDF</a> · '
        '<a href="../notebooks/01-write-finding.ipynb">notebook</a> · '
        f'<a href="{DASHBOARD_URL}">Gradio dashboard</a> '
        '<span id="dash-note" class="mut"></span> · '
        '<a href="https://github.com/thrmnn/embodimetry">repo</a></div>'
    )


COCKPIT_CSS = """
.strip{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 6px;align-items:center}
.strip.dagrow{margin:0 0 14px}
.chip{display:inline-block;padding:3px 10px;border-radius:12px;font-size:12px;font-weight:600;
border:1px solid var(--line);background:var(--card);color:var(--ink);text-decoration:none}
.chip.fresh{border-color:var(--ok-ln);color:var(--ok);background:var(--ok-bg)}
.chip.amber{border-color:var(--amber-ln);color:var(--amber);background:var(--amber-bg)}
.chip.dim{opacity:.55}
.chip.btn{cursor:pointer;font-family:inherit}
.chip.dagc:hover{border-color:var(--accent)}
.banner{position:sticky;top:0;z-index:40;background:var(--amber);color:#fff;padding:6px 12px;
border-radius:6px;font-size:13px;margin:10px 0}
.needs{border:2px solid var(--warn-ln);border-radius:10px;padding:4px 14px 10px;margin:14px 0;
background:var(--warn-bg)}
.needs h2{border:none;margin:8px 0 6px;font-size:15px}
.needs.amber{border-color:var(--amber-ln);background:var(--amber-bg)}
.needs.dim{opacity:.55}
.need{margin:4px 0}
.mut{color:var(--mut);font-size:12px}
.trk{border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:8px 0;
background:var(--card)}
.trk.dim{opacity:.6}
.st{font-weight:700;font-size:12px;text-transform:uppercase}
.st.done{color:var(--ok)}.st.running{color:var(--pend)}
.st.failed,.st.blocked{color:var(--warn)}.st.awaiting-theo{color:var(--amber)}
.gate{display:inline-block;font-size:11px;border:1px solid var(--line);border-radius:9px;
padding:1px 7px;margin:3px 4px 0 0}
.gate.pass{color:var(--ok);border-color:var(--ok-ln)}
.gate.fail{color:var(--warn);border-color:var(--warn-ln)}
ul.ms{margin:6px 0 0;padding-left:18px;font-size:12px;color:var(--mut)}
.bar{height:10px;background:var(--line);border-radius:5px;overflow:hidden;margin:6px 0}
.bar>div{height:100%;background:var(--accent)}
.linkrow{margin:26px 0 0;font-size:14px}
table.mini{border-collapse:collapse;font-size:14px;margin:8px 0}
table.mini th,table.mini td{border:1px solid var(--line);padding:4px 10px;text-align:left}
.pr{margin:6px 0}
#prs h3{border:none;margin:16px 0 4px}
"""

# One staleness rule: every payload timestamp is rendered as a client-computed
# age at view time. The build-age chip is load-bearing — it is the only honest
# signal when heartbeat rsyncs keep landing while full pushes silently fail.
COCKPIT_JS = """
(() => {
"use strict";
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const esc = (s) => String(s).replace(/[&<>"']/g,
  (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const SYM = {idle:"\\u00b7", running:"\\u25b6", blocked:"\\u25a0",
  "awaiting-theo":"\\u270b", done:"\\u2713", failed:"\\u2717"};
const fmtAge = (ms) => {
  const s = ms / 1000;
  if (s < 90) return Math.max(0, Math.round(s)) + "s";
  if (s < 5400) return Math.round(s / 60) + "m";
  if (s < 172800) return (s / 3600).toFixed(1) + "h";
  return (s / 86400).toFixed(1) + "d";
};
const age = (t) => fmtAge(Date.now() - Date.parse(t));
const tier = (t) => {
  const h = (Date.now() - Date.parse(t)) / 3.6e6;
  return h < 4.5 ? "fresh" : h < 9 ? "amber" : "dim";
};
function paintAges() {
  $$("[data-ts]").forEach((e) => {
    if (!Date.parse(e.dataset.ts)) return;
    e.textContent = (e.dataset.pre || "") + age(e.dataset.ts) + " ago";
  });
}
function chip(id, cls, ts, pre) {
  const e = $(id);
  if (!e) return;
  if (ts) e.dataset.ts = ts;
  if (pre !== undefined) e.dataset.pre = pre;
  e.className = "chip " + cls;
}
async function pollBuild() {
  const c = $("#chip-build"), b = $("#banner");
  try {
    const r = await fetch("/build.json", {cache: "no-store"});
    if (!r.ok) throw 0;
    const j = await r.json();
    chip("#chip-build", tier(j.built_at), j.built_at, "build ");
    c.title = j.build_id;
    b.hidden = true;
  } catch {
    chip("#chip-build", "dim", undefined, "build (cached) ");
    b.textContent = "offline or Tailscale disconnected \\u2014 cached copy from " +
      new Date(Date.parse(c.dataset.ts)).toLocaleString();
    b.hidden = false;
  }
  paintAges();
}
function renderFleet(f) {
  const tf = tier(f.generated_at);
  chip("#chip-fleet", tf, f.generated_at, "fleet ");
  $("#chip-fleet").title = tf === "fresh" ? "orchestrator live" :
    tf === "amber" ? "orchestrator quiet" :
    "orchestrator down or laptop asleep \\u2014 state as of " + f.generated_at;
  chip("#chip-dash", f.dashboard_up ? tf : "dim", f.generated_at,
    "dashboard " + (f.dashboard_up ? "up" : "down") + " \\u00b7 seen ");
  const note = $("#dash-note");
  if (note) note.textContent = f.dashboard_up ?
    "(last seen up " + age(f.generated_at) + " ago)" : "(laptop asleep \\u2014 expected)";
  const nb = $("#needs-theo");
  const needs = f.needs_theo || [];
  nb.hidden = !needs.length;
  nb.className = "needs " + (tf === "fresh" ? "" : tf);
  if (needs.length) nb.innerHTML = "<h2>Needs Th\\u00e9o</h2>" + needs.map((n) =>
    `<div class="need"><strong>${esc(n.track)}</strong> \\u2014 ${esc(n.ask)} ` +
    `<span class="mut">since ${esc(n.since)} ` +
    `(<span data-ts="${esc(n.since)}" data-pre="as of "></span>)</span></div>`).join("");
  $("#fleet-pane").innerHTML = f.tracks.map((t) => {
    const gates = (t.gates || []).map((g) =>
      `<span class="gate ${esc(g.status)}" title="${esc(g.evidence || "")}">` +
      `${esc(g.name)}</span>`).join("");
    const ms = (t.milestones || []).slice(-3).reverse().map((m) =>
      `<li><span data-ts="${esc(m.ts)}"></span> \\u2014 ` +
      (m.link ? `<a href="${esc(m.link)}">${esc(m.text)}</a>` : esc(m.text)) + "</li>").join("");
    return `<div class="trk ${tf === "dim" ? "dim" : ""}">` +
      `<span class="st ${esc(t.state)}">${SYM[t.state] || "\\u00b7"} ${esc(t.state)}</span> ` +
      `<strong>${esc(t.title || t.id)}</strong>` +
      `<div class="mut">${esc(t.now || "")}` +
      (t.last_event_at ? ` \\u00b7 <span data-ts="${esc(t.last_event_at)}"></span>` : "") +
      `</div>${gates}${ms ? `<ul class="ms">${ms}</ul>` : ""}</div>`;
  }).join("");
  if (f.sweeps && f.sweeps.length) $("#sweep-orch").textContent =
    "orchestrator: " + f.sweeps.map((s) =>
      `${s.name} ${s.completed}/${s.total}${s.headline ? " \\u2014 " + s.headline : ""}`).join(" \\u00b7 ");
  paintAges();
}
async function pollFleet() {
  try {
    const r = await fetch("/fleet_status.json", {cache: "no-store"});
    if (!r.ok) throw 0;
    renderFleet(await r.json());
  } catch {}
}
function renderPRs(data) {
  const states = [];
  $$("#pr-pane .pr").forEach((el) => {
    const d = data[el.dataset.repo + "#" + el.dataset.num];
    if (!d) return;
    const cls = d.state === "open" ? "info" : d.merged ? "ok" : "warn";
    el.querySelector(".prx").innerHTML =
      `<span class="pill ${cls}">#${esc(el.dataset.num)} ${esc(d.merged ? "merged" : d.state)}` +
      `</span> ${esc(d.title)} <span class="mut">updated ` +
      `<span data-ts="${esc(d.updated_at)}"></span></span>`;
    states.push(`#${el.dataset.num} ${d.merged ? "merged" : d.state}`);
  });
  if (states.length) $("#chip-pr").textContent = states.join(" \\u00b7 ");
  paintAges();
}
async function pollPRs() {
  let data = {};
  try { data = JSON.parse(localStorage.getItem("cockpit-prs") || "{}"); } catch {}
  renderPRs(data);
  for (const el of $$("#pr-pane .pr")) {
    try {
      const r = await fetch(`https://api.github.com/repos/${el.dataset.repo}/pulls/${el.dataset.num}`);
      if (!r.ok) continue;  // a 403 rate-limit must never clobber the good copy
      const j = await r.json();
      data[el.dataset.repo + "#" + el.dataset.num] = {state: j.state, merged: j.merged,
        title: j.title, updated_at: j.updated_at};
      localStorage.setItem("cockpit-prs", JSON.stringify(data));
    } catch {}
  }
  renderPRs(data);
}
function refresh() { pollBuild(); pollFleet(); pollPRs(); }
addEventListener("DOMContentLoaded", () => {
  const b = $("#btn-refresh");
  if (b) b.addEventListener("click", refresh);
  paintAges();
  setInterval(paintAges, 60000);
  refresh();
  if ("serviceWorker" in navigator &&
      (location.protocol === "https:" || ["localhost", "127.0.0.1"].includes(location.hostname)))
    navigator.serviceWorker.register("/sw.js").catch(() => {});
});
})();
"""

SW_TEMPLATE = """\
const CACHE = "cockpit-__BUILD_ID__";
const PRECACHE = __PRECACHE__;
const NEVER = ["/build.json", "/fleet_status.json"];
self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});
self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  if (NEVER.includes(url.pathname)) return;
  const nav = e.request.mode === "navigate" ||
    url.pathname.endsWith(".html") || url.pathname.endsWith("/");
  if (nav) {
    e.respondWith(fetch(e.request, {cache: "no-cache"})
      .then((r) => {
        const copy = r.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
        return r;
      })
      .catch(() => caches.match(url.pathname)
        .then((r) => r || caches.match(url.pathname.replace(/\\/$/, "/index.html")))
        .then((r) => r || caches.match("/_hub/index.html"))));
    return;
  }
  e.respondWith(caches.match(url.pathname).then((r) => r ||
    fetch(e.request).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, copy));
      }
      return res;
    })));
});
"""

_PRECACHE_SUFFIXES = {".html", ".css", ".js", ".svg", ".webmanifest", ".png"}


def _precache_paths() -> list[str]:
    keep = []
    for p in sorted(STAGE.rglob("*")):
        if not p.is_file():
            continue
        rel = "/" + p.relative_to(STAGE).as_posix()
        if p.name in ("sw.js", "build.json", "fleet_status.json"):
            continue
        # Heavy doc figures (docs/assets), the PDF, and the notebook are
        # runtime-cached on first view instead of pinned into every install.
        if rel.startswith("/docs/assets/"):
            continue
        if p.suffix in _PRECACHE_SUFFIXES:
            keep.append(rel)
    return keep


def emit_stage(build_id: str, built_at: str, sha: str) -> int:
    if STAGE.exists():
        shutil.rmtree(STAGE)
    (STAGE / "_hub").mkdir(parents=True)
    shutil.copy2(OUT / "index.html", STAGE / "_hub" / "index.html")
    shutil.copytree(DOCS_OUT, STAGE / "_hub" / "docs")
    shutil.copytree(REPO / "site", STAGE / "site")
    shutil.copytree(REPO / "paper" / "deck", STAGE / "paper" / "deck")
    shutil.copytree(REPO / "docs" / "assets", STAGE / "docs" / "assets")
    shutil.copytree(REPO / "assets" / "hub-icons", STAGE / "assets" / "hub-icons")
    if (REPO / "paper/main.pdf").exists():
        shutil.copy2(REPO / "paper/main.pdf", STAGE / "paper" / "main.pdf")
    notebook = REPO / "notebooks/01-write-finding.ipynb"
    if notebook.exists():
        (STAGE / "notebooks").mkdir()
        shutil.copy2(notebook, STAGE / "notebooks" / notebook.name)
    if (OUT / "fleet_status.json").exists():
        shutil.copy2(OUT / "fleet_status.json", STAGE / "fleet_status.json")
    (STAGE / "build.json").write_text(
        json.dumps({"build_id": build_id, "built_at": built_at, "git_sha": sha}) + "\n"
    )
    manifest = {
        "name": "embodimetry cockpit",
        "short_name": "embodimetry",
        "start_url": "/_hub/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#12161a",
        "theme_color": "#1a6fb5",
        "icons": [
            {"src": "/assets/hub-icons/icon-192.png", "sizes": "192x192", "type": "image/png"},
            {"src": "/assets/hub-icons/icon-512.png", "sizes": "512x512", "type": "image/png"},
        ],
    }
    (STAGE / "manifest.webmanifest").write_text(json.dumps(manifest) + "\n")
    precache = _precache_paths()
    (STAGE / "sw.js").write_text(
        SW_TEMPLATE.replace("__BUILD_ID__", build_id).replace("__PRECACHE__", json.dumps(precache))
    )
    return len(precache)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docs = render_docs()
    prov = hk.git_provenance(REPO, GENERATOR)
    sha = _git("rev-parse", "HEAD") or "unknown"
    built_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    build_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S") + "-" + sha[:8]
    fleet = _read_fleet()

    # --- Ship-readiness rendered inline, not just linked -------------------
    ship_md = (REPO / "docs/SHIP_READINESS.md").read_text()
    ship_body = hk.md_to_html(ship_md, base=["docs", "SHIP_READINESS.md"][0])
    ship_inline = f'<section id="ship-readiness"><h2>Ship readiness (live)</h2><div class="doc">{ship_body}</div></section>'

    # --- User-facing --------------------------------------------------------
    # HF Space/dataset are plain links, no up/down claim: a build-time probe
    # boolean with no timestamp is a lie by Tuesday on a push-model cockpit.
    user_cards = [
        hk.card(
            "Public leaderboard (HF Space)",
            "Leaderboard, paired comparisons, rollout browser, failure taxonomy. "
            "Creation is user-gated; link 404s until it exists.",
            "https://huggingface.co/spaces/thrmnn/embodimetry",
            kind="doc",
            meta="huggingface.co/spaces/thrmnn/embodimetry",
        ),
        hk.card(
            "Hub dataset",
            "Per-episode outcomes + rollout MP4s, queryable by (policy, env, seed, episode). "
            "Publish pending Théo's decision.",
            "https://huggingface.co/datasets/thrmnn/embodimetry-v1",
            kind="doc",
            meta="huggingface.co/datasets/thrmnn/embodimetry-v1",
        ),
        hk.card(
            "Landing page (site/)",
            "Static narrative page for recruiters/researchers — hero, artifacts, "
            "headline finding. GitHub Pages not enabled yet; served locally here.",
            "../site/index.html",
            kind="amber",
            meta="site/index.html — Pages: not enabled",
        ),
        hk.card(
            "arXiv paper (PDF)",
            "Methodology, results, limitations. arXiv ID still TBD.",
            "../paper/main.pdf",
            kind="doc",
            meta="paper/main.pdf",
        ),
    ]

    # --- Presentation ---------------------------------------------------------
    deck_cards = [
        hk.card(
            "Slide deck",
            "Self-contained HTML presentation deck.",
            "../paper/deck/index.html",
            kind="doc",
            meta="paper/deck/index.html",
        ),
        hk.card(
            "Paper source (LaTeX)",
            "main.tex — compile with `make -C paper`.",
            "https://github.com/thrmnn/embodimetry/blob/main/paper/main.tex",
            kind="doc",
            meta="paper/main.tex",
        ),
    ]

    # --- Dev / ops --------------------------------------------------------
    dev_cards = [
        hk.card(
            "Operator dashboard (dev)",
            "Live sweep progress, calibration inspector, rollout preview, log tail. "
            "Reachable only while the laptop is awake and on the tailnet — "
            "status chip above reports last-seen state from the fleet heartbeat.",
            DASHBOARD_URL,
            kind="info",
            meta=f"{DASHBOARD_URL} (tailnet only)",
        ),
        hk.card(
            "Analysis notebook",
            "notebooks/01-write-finding.ipynb — re-run top to bottom against the "
            "real parquet before any release. Open locally with Jupyter.",
            "../notebooks/01-write-finding.ipynb",
            kind="doc",
            meta="notebooks/01-write-finding.ipynb",
        ),
        hk.card(
            "Runbook",
            "Day-to-day sweep ops, GPU preflight, release cut, worktree prune.",
            docs.get("runbook", "#"),
            kind="doc",
        ),
        hk.card(
            "Publish runbook",
            "One-command-per-step v1 Hub publish sequence, owner-gated steps marked.",
            docs.get("publish-runbook", "#"),
            kind="doc",
        ),
        hk.card(
            "Pipeline roadmap",
            "What's next past v1.0 — publish chain, v1.1 coverage, upstream PR, WM track.",
            docs.get("pipeline-roadmap", "#"),
            kind="doc",
        ),
        hk.card(
            "Architecture",
            "How the eval/env/policy registries and checkpointing fit together.",
            docs.get("architecture", "#"),
            kind="doc",
        ),
        hk.card(
            "Design",
            "Methodology: stats, MDE bounds, failure taxonomy design.",
            docs.get("design", "#"),
            kind="doc",
        ),
        hk.card(
            "Changelog", "Notable changes per release.", docs.get("changelog", "#"), kind="doc"
        ),
        hk.card(
            "GitHub repo",
            "Source, issues, PRs, Actions.",
            "https://github.com/thrmnn/embodimetry",
            kind="doc",
        ),
    ]

    paper_dag_section, dag_statuses = render_paper_dag()
    pr_pane, prs = render_pr_pane(fleet)

    body = (
        render_strip(built_at, fleet, dag_statuses, prs)
        + render_needs_theo(fleet)
        + render_fleet_pane(fleet)
        + render_sweep_pane(fleet)
        + render_results_pane(docs)
        + pr_pane
        + ship_inline
        + hk.section("User-facing", user_cards, anchor="user-facing")
        + hk.section("Presentation & paper", deck_cards, anchor="presentation")
        + paper_dag_section
        + hk.section("Dev / ops", dev_cards, anchor="dev-ops")
        + render_linkrow(fleet)
    )

    sidebar = hk.toc_sections(
        [
            ("fleet", "Fleet"),
            ("sweep", "Sweep"),
            ("results", "Headline results"),
            ("prs", "PRs & activity"),
            ("ship-readiness", "Ship readiness"),
            ("user-facing", "User-facing"),
            ("presentation", "Presentation & paper"),
            ("paper-dag", "Paper DAG"),
            ("dev-ops", "Dev / ops"),
        ]
    )

    head_extra = (
        '<link rel="manifest" href="/manifest.webmanifest">'
        '<meta name="theme-color" content="#1a6fb5">'
        '<link rel="apple-touch-icon" href="/assets/hub-icons/icon-192.png">'
        f"<style>{COCKPIT_CSS}</style><script>{COCKPIT_JS}</script>"
    )
    html_out = hk.page(
        "embodimetry — cockpit",
        "One entry point: fleet, sweeps, results, dashboards, paper, and docs. "
        "Regenerate with <code>python scripts/build_project_hub.py</code>.",
        body,
        provenance=prov,
        sidebar=sidebar,
        head_extra=head_extra,
    )
    (OUT / "index.html").write_text(html_out)
    n = emit_stage(build_id, built_at, sha)
    print(f"wrote {OUT / 'index.html'}")
    print(f"staged {STAGE} · build {build_id} · {n} precached files")


if __name__ == "__main__":
    main()
