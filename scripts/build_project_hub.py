"""Builds the single orchestration entry-point hub tying together every
embodimetry surface: dev dashboard, public Space, static site, deck, paper,
and the living docs. Pure navigation layer — never edit _hub/*.html by hand,
edit this script and re-run it.

    python scripts/build_project_hub.py

Serve the repo root so root-relative links resolve to the other surfaces:

    python -m http.server 8888 --bind 0.0.0.0
    # hub:  http://<host>:8888/_hub/index.html
"""

from __future__ import annotations

import re
import urllib.request
from pathlib import Path

import yaml

import hubkit as hk

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "_hub"
DOCS_OUT = OUT / "docs"
GENERATOR = "scripts/build_project_hub.py"

_FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)

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


def _probe(url: str, timeout: float = 2.0) -> bool:
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def _crumb() -> str:
    return hk.breadcrumb([("embodimetry hub", "../index.html"), ("doc", None)])


def _frontmatter(md_path: Path) -> dict:
    m = _FRONTMATTER.match(md_path.read_text())
    if not m:
        return {}
    data = yaml.safe_load(m.group(1))
    return data if isinstance(data, dict) else {}


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


def render_paper_dag() -> str:
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
    return hk.section("Paper DAG (academic-paper-workflow)", cards, anchor="paper-dag")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    docs = render_docs()
    prov = hk.git_provenance(REPO, GENERATOR)

    dashboard_up = _probe("http://127.0.0.1:7860/")
    space_up = _probe("https://huggingface.co/spaces/thrmnn/embodimetry")
    dataset_up = _probe("https://huggingface.co/api/datasets/thrmnn/embodimetry-v1")

    # --- Ship-readiness rendered inline, not just linked -------------------
    ship_md = (REPO / "docs/SHIP_READINESS.md").read_text()
    ship_body = hk.md_to_html(ship_md, base=["docs", "SHIP_READINESS.md"][0])
    ship_inline = f'<section id="ship-readiness"><h2>Ship readiness (live)</h2><div class="doc">{ship_body}</div></section>'

    # --- User-facing --------------------------------------------------------
    user_cards = [
        hk.card(
            "Public leaderboard (HF Space)",
            "Leaderboard, paired comparisons, rollout browser, failure taxonomy."
            + ("" if space_up else " Not deployed yet — create + `make space-deploy`."),
            "https://huggingface.co/spaces/thrmnn/embodimetry",
            kind="ok" if space_up else "warn",
            meta="huggingface.co/spaces/thrmnn/embodimetry",
        ),
        hk.card(
            "Hub dataset",
            "Per-episode outcomes + rollout MP4s, queryable by (policy, env, seed, episode)."
            + ("" if dataset_up else " Repo not found."),
            "https://huggingface.co/datasets/thrmnn/embodimetry-v1",
            kind="ok" if dataset_up else "warn",
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
            "4-page writeup: methodology, results, limitations. arXiv ID still TBD.",
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
            "Live sweep progress, calibration inspector, rollout preview, log tail."
            + ("" if dashboard_up else " Not running — `make dashboard`."),
            "http://127.0.0.1:7860/",
            kind="ok" if dashboard_up else "warn",
            meta="Tailscale: http://100.104.205.62:7860 (same tailnet only)",
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

    paper_dag_section = render_paper_dag()

    body = (
        ship_inline
        + hk.section("User-facing", user_cards, anchor="user-facing")
        + hk.section("Presentation & paper", deck_cards, anchor="presentation")
        + paper_dag_section
        + hk.section("Dev / ops", dev_cards, anchor="dev-ops")
    )

    sidebar = hk.toc_sections(
        [
            ("ship-readiness", "Ship readiness"),
            ("user-facing", "User-facing"),
            ("presentation", "Presentation & paper"),
            ("paper-dag", "Paper DAG"),
            ("dev-ops", "Dev / ops"),
        ]
    )

    html = hk.page(
        "embodimetry — orchestration hub",
        "One entry point: dashboards, public surfaces, presentation, and docs. "
        "Regenerate with <code>python scripts/build_project_hub.py</code>.",
        body,
        provenance=prov,
        sidebar=sidebar,
    )
    (OUT / "index.html").write_text(html)
    print(f"wrote {OUT / 'index.html'}")
    print(f"dashboard up: {dashboard_up} · space up: {space_up} · dataset up: {dataset_up}")


if __name__ == "__main__":
    main()
