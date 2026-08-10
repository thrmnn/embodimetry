"""hubkit — zero-dependency static hub / review-dashboard engine.

Vendored from the `project-hub` skill (~/.claude/skills/project-hub/). The design
system (semantic :root vars, card/grid/pill/crumb components, provenance footer)
is adapted from the Airflow reporting repo. No third-party deps — pure stdlib —
so a generated hub is a single portable artifact and the engine drops into any
project's env unchanged.

Public API: `page`, `card`, `section`, `badge`, `breadcrumb`, `md_to_html`,
`render_doc_page`, `git_provenance`.
"""

from __future__ import annotations

import html as _html
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

CSS = """
:root{--ink:#1a1d21;--mut:#5b6470;--line:#e3e7ec;--accent:#1a6fb5;--ok:#1a7f4b;
--warn:#b3261e;--amber:#9a5b00;--pend:#1f5fa8;--bg:#fbfcfd;--card:#fff;--lh:1.6;
--img-line:#eee;--faint:#9aa;--code-bg:#f3f5f7;--th-bg:#eef1f4;--row-alt:#fafbfc;
--pre-bg:#1d2127;--pre-ink:#e6e9ee;--doc-ink:#2a2d31;--doc-lede:#444;
--ok-bg:#e6f4ec;--ok-ln:#bfe2cd;--warn-bg:#fdeceb;--warn-ln:#f3c9c5;
--amber-bg:#fbf1e0;--amber-ln:#ecd9b3;--info-bg:#e8f1fb;--info-ln:#c7ddf5;
--doc-bg:#eef0f2;--doc-ln:#dde1e5}
@media(prefers-color-scheme:dark){:root{--ink:#e2e6ea;--mut:#9aa4af;--line:#2b323a;
--accent:#63a9e6;--ok:#53c48d;--warn:#ef7d75;--amber:#d9a850;--pend:#82b6ec;
--bg:#12161a;--card:#191f25;--img-line:#2b323a;--faint:#6d7883;--code-bg:#242b33;
--th-bg:#202730;--row-alt:#1d242b;--pre-bg:#0c0f12;--pre-ink:#dde2e7;
--doc-ink:#cfd6dc;--doc-lede:#aeb7bf;--ok-bg:#15342a;--ok-ln:#245c41;
--warn-bg:#3d1f1e;--warn-ln:#6e3330;--amber-bg:#3a2c14;--amber-ln:#6b5426;
--info-bg:#16283c;--info-ln:#2a4a6e;--doc-bg:#232a31;--doc-ln:#333c45}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font:16px/var(--lh) -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1040px;margin:0 auto;padding:20px 22px 80px}
header.hd{border-bottom:2px solid var(--ink);padding-bottom:12px;margin-bottom:6px}
header.hd h1{font-size:24px;margin:0 0 4px}
.sub{color:var(--mut);font-size:13px}
.crumb{position:sticky;top:0;z-index:20;background:var(--card);border-bottom:1px solid var(--line);
margin:0 -22px 18px;padding:10px 22px;font-size:14px;font-weight:600}
.crumb a{color:var(--accent);text-decoration:none}.crumb a:hover{text-decoration:underline}
.crumb .sep{color:var(--mut);margin:0 8px;font-weight:400}.crumb .here{color:var(--mut)}
h2{font-size:18px;margin:30px 0 12px;padding-bottom:5px;border-bottom:1px solid var(--line)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;
overflow:hidden;text-decoration:none;color:inherit;transition:.12s;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.card:hover{border-color:var(--accent);transform:translateY(-2px);box-shadow:0 4px 14px rgba(0,0,0,.08)}
.card img{width:100%;display:block;border-bottom:1px solid var(--img-line);cursor:zoom-in}
.cap{padding:13px 15px}.cap h3{margin:6px 0 4px;font-size:15px}
.cap p{margin:0;color:var(--mut);font-size:13px}.cap code{font-size:11px;color:var(--faint)}
.pill{display:inline-block;padding:2px 8px;border-radius:11px;font-size:11px;font-weight:700;
text-transform:uppercase;letter-spacing:.03em;border:1px solid transparent}
.pill.ok{background:var(--ok-bg);color:var(--ok);border-color:var(--ok-ln)}
.pill.warn{background:var(--warn-bg);color:var(--warn);border-color:var(--warn-ln)}
.pill.amber{background:var(--amber-bg);color:var(--amber);border-color:var(--amber-ln)}
.pill.info{background:var(--info-bg);color:var(--pend);border-color:var(--info-ln)}
.pill.doc{background:var(--doc-bg);color:var(--mut);border-color:var(--doc-ln)}
footer{margin-top:40px;padding-top:16px;border-top:1px solid var(--line);color:var(--faint);font-size:12px}
.doc{max-width:820px}.doc h1{font-size:24px}.doc h2{font-size:19px}.doc h3{font-size:16px}
.doc table{border-collapse:collapse;margin:14px 0;font-size:14px;width:100%}
.doc th,.doc td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}
.doc th{background:var(--th-bg)}.doc code{background:var(--code-bg);padding:1px 5px;border-radius:4px;font-size:13px}
.doc pre{background:var(--pre-bg);color:var(--pre-ink);padding:14px;border-radius:8px;overflow:auto;font-size:13px}
.doc pre code{background:none;color:inherit;padding:0}.doc blockquote{border-left:3px solid var(--line);
margin:0;padding:2px 14px;color:var(--mut)}
.doc{font-size:15.5px;color:var(--doc-ink)}
.doc h1{font-size:25px;line-height:1.2;margin:0 0 4px}
.doc h2{margin:34px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--ink)}
.doc h3{margin:22px 0 8px;color:var(--accent)}
.doc>p:first-of-type{font-size:17px;color:var(--doc-lede);line-height:1.6}
.doc img{max-width:100%;height:auto;display:block;margin:18px auto 4px;border:1px solid var(--line);
border-radius:8px;box-shadow:0 1px 6px rgba(0,0,0,.06)}
/* an italics-only paragraph right after a figure reads as its caption */
.doc img+p em:only-child,.doc p>em:only-child{display:block;text-align:center;font-size:13px;
color:var(--mut);margin:0 auto 18px;max-width:80%;font-style:italic}
.doc table{box-shadow:0 1px 4px rgba(0,0,0,.05)}.doc th{background:var(--th-bg)}
.doc tr:nth-child(even) td{background:var(--row-alt)}
.doc strong{color:var(--ink)}
#lb{display:none;position:fixed;inset:0;background:rgba(0,0,0,.9);z-index:99;cursor:zoom-out;
align-items:center;justify-content:center}#lb img{max-width:96vw;max-height:94vh}
.layout{display:flex;align-items:flex-start;max-width:1320px;margin:0 auto}
.layout aside{position:sticky;top:0;flex:0 0 240px;max-height:100vh;overflow:auto;
padding:22px 10px 22px 22px}
.layout main{flex:1 1 auto;min-width:0}
.toc{font-size:13px;border-left:2px solid var(--line);padding-left:12px}
.toc-h{font-weight:700;color:var(--mut);text-transform:uppercase;letter-spacing:.04em;
font-size:11px;margin-bottom:8px}
.toc a{display:block;color:var(--mut);text-decoration:none;padding:3px 0;line-height:1.35}
.toc a:hover{color:var(--accent)}
.toc a.t3{padding-left:12px;font-size:12px}
html{scroll-behavior:smooth}:target{scroll-margin-top:14px}
@media(max-width:820px){.layout{display:block}.layout aside{position:static;max-height:none;
flex-basis:auto;padding:14px 22px 0}.toc{border-left:none;border-bottom:1px solid var(--line);
padding:0 0 10px}.toc a{display:inline-block;margin-right:14px}}
"""

_LB = (
    "<div id=lb onclick=\"this.style.display='none'\"><img id=lbi></div>"
    "<script>function zoom(s){lbi.src=s;lb.style.display='flex'}"
    "addEventListener('keydown',e=>{if(e.key=='Escape')lb.style.display='none'})</script>"
)


def badge(kind: str, label: str) -> str:
    return f'<span class="pill {kind}">{_html.escape(label)}</span>'


def card(title, desc, href, *, meta="", img=None, kind="doc") -> str:
    imgtag = (
        f'<img src="{img}" loading="lazy" onclick="event.preventDefault();zoom(\'{img}\')">'
        if img
        else ""
    )
    metatag = f"<br><code>{_html.escape(meta)}</code>" if meta else ""
    # Relative hrefs stay same-tab so an installed PWA doesn't escape to browser tabs.
    target = ' target="_blank"' if re.match(r"^https?:", href) else ""
    return (
        f'<a class="card" href="{href}"{target}>{imgtag}'
        f'<div class="cap">{badge(kind, kind)}<h3>{_html.escape(title)}</h3>'
        f"<p>{_html.escape(desc)}{metatag}</p></div></a>"
    )


def section(title: str, cards: list[str], anchor: str | None = None) -> str:
    if not cards:
        return ""
    aid = f' id="{anchor}"' if anchor else ""
    return f'<section><h2{aid}>{_html.escape(title)}</h2><div class="grid">{"".join(cards)}</div></section>'


def breadcrumb(trail: list[tuple[str, str | None]]) -> str:
    parts = []
    for i, (label, href) in enumerate(trail):
        if href and i < len(trail) - 1:
            parts.append(f'<a href="{href}">{_html.escape(label)}</a>')
        else:
            parts.append(f'<span class="here">{_html.escape(label)}</span>')
    return '<nav class="crumb">' + '<span class="sep">›</span>'.join(parts) + "</nav>"


def _slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    return re.sub(r"\s+", "-", s.strip())[:60] or "section"


def toc_from_html(body: str, levels=("h2", "h3")) -> str:
    """Sidebar table of contents from `<hN id=...>` headings in rendered HTML."""
    items = re.findall(r'<(h[23]) id="([^"]+)">(.*?)</h[23]>', body, re.DOTALL)
    if not items:
        return ""
    rows = []
    for tag, hid, txt in items:
        txt = re.sub(r"<[^>]+>", "", txt).strip()
        cls = "t3" if tag == "h3" else "t2"
        rows.append(f'<a class="{cls}" href="#{hid}">{_html.escape(txt)}</a>')
    return '<nav class="toc"><div class="toc-h">On this page</div>' + "".join(rows) + "</nav>"


def toc_sections(sections: list[tuple[str, str]]) -> str:
    """Sidebar TOC from explicit (anchor, label) pairs — for hub/gallery pages."""
    rows = [f'<a class="t2" href="#{a}">{_html.escape(lbl)}</a>' for a, lbl in sections]
    return '<nav class="toc"><div class="toc-h">Sections</div>' + "".join(rows) + "</nav>"


def page(
    title, subtitle, body, *, crumb="", provenance="", doc=False, sidebar="", head_extra=""
) -> str:
    cls = "wrap doc" if doc else "wrap"
    foot = f"<footer>{_html.escape(provenance)}</footer>" if provenance else ""
    main = (
        f'<div class="layout"><aside>{sidebar}</aside>'
        f'<main class="{cls}">{crumb}'
        f"<header class=hd><h1>{_html.escape(title)}</h1>"
        f"<div class=sub>{subtitle}</div></header>{body}{foot}</main></div>"
        if sidebar
        else f'<div class="{cls}">{crumb}'
        f"<header class=hd><h1>{_html.escape(title)}</h1>"
        f"<div class=sub>{subtitle}</div></header>{body}{foot}</div>"
    )
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>{_html.escape(title)}</title><style>{CSS}</style>{head_extra}</head><body>
{main}{_LB}</body></html>"""


def git_provenance(repo: Path, generator: str) -> str:
    def g(*a):
        try:
            return (
                subprocess.check_output(["git", *a], cwd=repo, stderr=subprocess.DEVNULL)
                .decode()
                .strip()
            )
        except Exception:
            return "?"

    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    return (
        f"Generated by {generator} · branch {g('rev-parse', '--abbrev-ref', 'HEAD')} "
        f"· {g('rev-parse', '--short', 'HEAD')} · {now} · regenerate to refresh."
    )


# --- minimal, dependency-free Markdown → HTML (headings, lists, tables, code,
#     inline emphasis/links). Good enough for project docs; not a spec parser. ---
def _rel(url: str, base: str) -> str:
    if base and not re.match(r"^(/|https?:|#|mailto:)", url):
        return base.rstrip("/") + "/" + url
    return url


def _inline(t: str, base: str = "") -> str:
    t = _html.escape(t)
    t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
    t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
    t = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", t)
    t = re.sub(
        r"!\[([^\]]*)\]\(([^)]+)\)",
        lambda m: f'<img src="{_rel(m.group(2), base)}" alt="{m.group(1)}">',
        t,
    )
    t = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        lambda m: f'<a href="{_rel(m.group(2), base)}">{m.group(1)}</a>',
        t,
    )
    return t


_UL = re.compile(r"^\s*[-*]\s+")
_OL = re.compile(r"^\s*\d+\.\s+")


def md_to_html(md: str, base: str = "") -> str:
    def inl(s):
        return _inline(s, base)

    lines = md.splitlines()
    out, i = [], 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            buf = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                buf.append(_html.escape(lines[i]))
                i += 1
            out.append("<pre><code>" + "\n".join(buf) + "</code></pre>")
        elif re.match(r"^#{1,6}\s", ln):
            n = len(ln) - len(ln.lstrip("#"))
            txt = ln[n:].strip()
            hid = _slug(txt)
            out.append(f'<h{n} id="{hid}">{inl(txt)}</h{n}>')
        elif _UL.match(ln):
            buf = []
            while i < len(lines) and _UL.match(lines[i]):
                buf.append(f"<li>{inl(_UL.sub('', lines[i]))}</li>")
                i += 1
            out.append("<ul>" + "".join(buf) + "</ul>")
            continue
        elif _OL.match(ln):
            buf = []
            while i < len(lines) and _OL.match(lines[i]):
                buf.append(f"<li>{inl(_OL.sub('', lines[i]))}</li>")
                i += 1
            out.append("<ol>" + "".join(buf) + "</ol>")
            continue
        elif "|" in ln and i + 1 < len(lines) and re.match(r"^\s*\|?[\s:|-]+\|?\s*$", lines[i + 1]):

            def cells(row):
                return [c.strip() for c in row.strip().strip("|").split("|")]

            head = cells(ln)
            i += 2
            body = []
            while i < len(lines) and "|" in lines[i]:
                body.append(cells(lines[i]))
                i += 1
            th = "".join(f"<th>{inl(c)}</th>" for c in head)
            trs = "".join("<tr>" + "".join(f"<td>{inl(c)}</td>" for c in r) + "</tr>" for r in body)
            out.append(f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>")
            continue
        elif re.match(r"^\s*---+\s*$", ln):
            out.append("<hr>")
        elif ln.strip() == "":
            pass
        else:
            buf = [ln]
            while (
                i + 1 < len(lines)
                and lines[i + 1].strip()
                and not re.match(
                    r"^(#{1,6}\s|```|\s*[-*]\s|\s*\d+\.\s|>|\s*---+\s*$)", lines[i + 1]
                )
            ):
                i += 1
                buf.append(lines[i])
            out.append("<p>" + inl(" ".join(buf)) + "</p>")
        i += 1
    return "\n".join(out)


def render_doc_page(md_path: Path, out_path: Path, *, crumb="", provenance="", base="") -> None:
    text = Path(md_path).read_text()
    title = next(
        (ln.lstrip("# ").strip() for ln in text.splitlines() if ln.startswith("# ")),
        Path(md_path).stem,
    )
    body = md_to_html(text, base=base)
    out_path.write_text(
        page(
            title,
            f"source: {md_path.name}",
            body,
            crumb=crumb,
            provenance=provenance,
            doc=True,
            sidebar=toc_from_html(body),
        )
    )
