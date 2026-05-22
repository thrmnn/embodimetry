"""Local-first sweep dashboard for the operator running an overnight sweep.

This is **not** the public-facing HF Space (that lives in ``space/``).
This dashboard runs on the operator's laptop, reads sweep state + videos
**from disk only** (no Hub fetches), and answers exactly one question:

    "I launched a ~20 h sweep and walked away -- is it healthy, or
    does it need me? Can I close the laptop and sleep?"

Three tabs:

1. **Status** (default landing) -- one auto-refreshing screen: a big
   green/amber/red health banner, a KPI strip, the per-cell progress
   grid, the live mini-leaderboard, anomaly alerts, the resource +
   throttle panel, and a folded raw-log accordion. The instant it
   loads, one plain-English sentence says whether the sweep needs the
   operator. Green = sleep, red = look.
2. **Pre-flight** -- the calibration inspector: the before-the-sweep
   latency / VRAM probe and the auto-downscope recommendations.
3. **Rollouts** -- a ``(policy, env, seed, episode)`` dropdown cascade
   into the MP4 archive for spot-checking what a policy actually does.

All non-trivial plumbing lives in :mod:`_helpers`. The companion
``tests/test_dashboard.py`` imports that module directly so the
dashboard's data layer is exercised without Gradio in the test
environment (Gradio is in the ``[space]`` extras but not ``[dev]``).
"""

from __future__ import annotations

import html
import logging
import os
from pathlib import Path
from typing import Any

import gradio as gr
import pandas as pd
from _helpers import (
    CALIBRATION_COLUMNS,
    DEFAULT_LOG_TAIL_LINES,
    DEFAULT_VIDEO_ROOTS,
    EPISODE_SELECT_FIRST,
    EPISODE_SELECT_REPRESENTATIVE,
    HEALTH_AMBER,
    HEALTH_GREEN,
    HEALTH_RED,
    LEADERBOARD_COLUMNS,
    PROGRESS_COLUMNS,
    AnomalyReport,
    MissionKPIs,
    StaleDataCache,
    ThrottleState,
    build_calibration_table,
    build_live_leaderboard,
    build_progress_table,
    clear_video_cache,
    column_glossary_markdown,
    compute_mission_kpis,
    discover_sweep_logs,
    discover_sweep_runs,
    env_dashboard_logs_dir,
    env_dashboard_results_dir,
    find_latest_calibration,
    find_video_path,
    format_bytes_gb,
    format_log_lines_html,
    leaderboard_dataframe,
    load_calibration_report,
    load_manifest,
    load_results_parquet,
    load_with_stale_fallback,
    per_tab_intro_markdown,
    read_system_memory,
    read_throttle_state,
    resolved_paths_banner_markdown,
    run_anomaly_review,
    scan_video_index,
    select_representative_episode,
    summarize_log,
    tail_log_lines,
    video_index_options,
)

logger = logging.getLogger("dashboard-app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# How often the Status screen repaints. 5 s is plenty for an overnight
# sweep; the manifest writer flushes every cell boundary, so anything
# tighter would just burn battery without showing fresher data.
STATUS_REFRESH_SECONDS = 5.0

# The raw-log accordion at the bottom of Status repaints on a faster
# cadence -- a log tail is the one place where a 2 s lag is noticeable.
LOG_REFRESH_SECONDS = 2.0

# Stable tab IDs for the ``gr.Tabs`` container. Strings so the layout
# is self-documenting; Status is the default landing tab.
STATUS_TAB_ID = "status"
PREFLIGHT_TAB_ID = "preflight"
ROLLOUTS_TAB_ID = "rollouts"

# --------------------------------------------------------------------- #
# Stale-data resilience cache                                           #
# --------------------------------------------------------------------- #
#
# One :class:`StaleDataCache` for the progress grid so it keeps showing
# last-known-good values when the manifest is mid-write. Module-level
# state is fine: the dashboard is single-tenant by design (one operator,
# one browser, one sweep) and the cache is derived purely from disk -- a
# process restart re-warms it on the first successful refresh.
_progress_cache = StaleDataCache()


def reset_stale_caches() -> None:
    """Reset the module-level progress cache (test seam)."""
    global _progress_cache
    _progress_cache = StaleDataCache()


# --------------------------------------------------------------------- #
# Newest-run discovery                                                  #
# --------------------------------------------------------------------- #


def _newest_manifest_path() -> Path | None:
    """Return the manifest path of the most recently started sweep run.

    This is the heart of the Status-screen auto-load: there is **no**
    run-selector dropdown. ``discover_sweep_runs`` already sorts runs by
    ``started_utc`` descending, so ``runs[0]`` is the live sweep. The
    Status screen calls this on every paint, so a sweep that starts
    after the dashboard is already open is picked up on the next tick
    with no operator action -- which was the bug the old Sweep-progress
    tab had (its dropdown defaulted to nothing and the table stayed
    empty mid-sweep).
    """
    runs = discover_sweep_runs(env_dashboard_results_dir())
    return runs[0].manifest_path if runs else None


# --------------------------------------------------------------------- #
# Status tab -- health banner + KPI strip                               #
# --------------------------------------------------------------------- #
#
# All the data shaping lives in ``_helpers.py``; the functions below
# only format the helper output into HTML / Dataframe components.

# Health-banner colours. Keyed on the _helpers HEALTH_* severities.
_HEALTH_BANNER_STYLE: dict[str, tuple[str, str, str]] = {
    # severity -> (background, text colour, leading glyph)
    HEALTH_GREEN: ("#16a34a", "#ffffff", "✓"),
    HEALTH_AMBER: ("#d97706", "#ffffff", "⚠"),
    HEALTH_RED: ("#dc2626", "#ffffff", "⚠"),
}


def _kpi_tile_html(label: str, value: str, *, danger: bool = False) -> str:
    """Render one big KPI tile. ``danger`` paints the value red."""
    value_colour = "#dc2626" if danger else "inherit"
    return (
        '<div style="flex:1;min-width:130px;padding:12px 16px;'
        'background:rgba(0,0,0,0.04);border-radius:10px;text-align:center">'
        f'<div style="font-size:12px;text-transform:uppercase;letter-spacing:0.5px;'
        f'color:#666;margin-bottom:4px">{html.escape(label)}</div>'
        f'<div style="font-size:26px;font-weight:700;line-height:1.1;'
        f'color:{value_colour}">{html.escape(value)}</div></div>'
    )


def _render_health_banner(kpis: MissionKPIs) -> str:
    """Render the prominent green/amber/red health banner as HTML.

    This banner *is* the product: it must answer "does the sweep need
    me?" in one plain-English sentence the instant the page loads.
    """
    bg, fg, glyph = _HEALTH_BANNER_STYLE.get(kpis.health, _HEALTH_BANNER_STYLE[HEALTH_AMBER])
    return (
        f'<div style="padding:20px 24px;border-radius:14px;background:{bg};'
        f"color:{fg};font-size:24px;font-weight:700;text-align:center;"
        f'margin-bottom:8px">{glyph}&nbsp;&nbsp;{html.escape(kpis.health_message)}</div>'
    )


def _render_kpi_strip(kpis: MissionKPIs) -> str:
    """Render the KPI tile strip as a flexbox HTML row."""
    tiles = [
        _kpi_tile_html(
            "Cells done",
            f"{kpis.cells_done}/{kpis.denom}  ({kpis.percent_done:.0f}%)",
        ),
        _kpi_tile_html("Cells failed", str(kpis.cells_failed), danger=kpis.cells_failed > 0),
        _kpi_tile_html("Running now", kpis.running_label),
        _kpi_tile_html("Elapsed", kpis.elapsed_label),
        _kpi_tile_html("ETA", kpis.eta_label),
        _kpi_tile_html(
            "Sweep state",
            kpis.state,
            danger=kpis.state == "THROTTLED-frozen",
        ),
    ]
    return '<div style="display:flex;flex-wrap:wrap;gap:10px">' + "".join(tiles) + "</div>"


def _render_anomaly_panel(report: AnomalyReport) -> str:
    """Render the anomaly-alerts section: green clean / red flagged list."""
    if report.error:
        return (
            '<div style="padding:12px 16px;border-radius:10px;'
            'background:rgba(0,0,0,0.04);color:#666;font-size:14px">'
            f"Anomaly review: {html.escape(report.error)}.</div>"
        )
    if report.ok:
        return (
            '<div style="padding:14px 18px;border-radius:10px;background:#16a34a;'
            'color:#fff;font-size:16px;font-weight:600">✓ No anomalies — '
            f"all {report.n_cells_reviewed} reviewed cell(s) look healthy.</div>"
        )
    items = "".join(f'<li style="margin:2px 0">{html.escape(line)}</li>' for line in report.lines)
    return (
        '<div style="padding:14px 18px;border-radius:10px;background:#dc2626;'
        'color:#fff;font-size:14px">'
        f'<div style="font-size:16px;font-weight:700;margin-bottom:6px">'
        f"⚠ {report.n_cells_flagged} cell(s) flagged "
        f"({report.n_cells_reviewed} reviewed)</div>"
        f'<ul style="margin:0;padding-left:20px">{items}</ul></div>'
    )


def _memory_bar(label: str, used: int | None, total: int | None) -> str:
    """Render a labelled used/total memory bar; ``-`` when undiscoverable."""
    if used is None or total is None or total <= 0:
        return (
            f'<div style="margin:6px 0"><b>{html.escape(label)}:</b> '
            "&mdash; <i>(not discoverable)</i></div>"
        )
    pct = min(100.0, used / total * 100.0)
    bar_colour = "#dc2626" if pct >= 90 else ("#d97706" if pct >= 75 else "#16a34a")
    return (
        f'<div style="margin:6px 0"><b>{html.escape(label)}:</b> '
        f"{format_bytes_gb(used)} / {format_bytes_gb(total)} ({pct:.0f}%)"
        '<div style="height:10px;border-radius:5px;background:rgba(0,0,0,0.08);'
        'margin-top:3px">'
        f'<div style="height:100%;width:{pct:.0f}%;border-radius:5px;'
        f'background:{bar_colour}"></div></div></div>'
    )


def _render_resource_panel(throttle: ThrottleState) -> str:
    """Render the resource + throttle section as HTML."""
    mem = read_system_memory()
    if mem is None:
        host_block = (
            '<div style="margin:6px 0"><b>Host RAM:</b> &mdash; '
            "<i>(/proc/meminfo unreadable)</i></div>"
        )
    else:
        host_block = _memory_bar("Host RAM", mem.used_bytes, mem.total_bytes)

    cgroup_block = _memory_bar(
        "Sweep cgroup memory",
        throttle.memory_current,
        throttle.memory_max,
    )

    if not throttle.running:
        throttle_line = "<b>Throttle state:</b> sweep process not running"
    elif throttle.frozen is None:
        throttle_line = (
            f"<b>Throttle state:</b> sweep running (PID {throttle.pid}); "
            "cgroup freeze state not discoverable"
        )
    elif throttle.frozen:
        throttle_line = (
            f'<b>Throttle state:</b> <span style="color:#dc2626;font-weight:700">'
            f"FROZEN</span> (PID {throttle.pid}) — watchdog throttled the sweep"
        )
    else:
        throttle_line = (
            f'<b>Throttle state:</b> <span style="color:#16a34a;font-weight:700">'
            f"RUNNING</span> (PID {throttle.pid})"
        )

    return (
        '<div style="padding:12px 16px;border-radius:10px;'
        'background:rgba(0,0,0,0.04);font-size:14px">'
        + host_block
        + cgroup_block
        + f'<div style="margin:6px 0">{throttle_line}</div></div>'
    )


# --------------------------------------------------------------------- #
# Status tab -- per-cell progress grid                                  #
# --------------------------------------------------------------------- #


def _empty_progress_table() -> pd.DataFrame:
    """A zero-row progress dataframe with the canonical columns."""
    return pd.DataFrame({c: [] for c in PROGRESS_COLUMNS})


def _summarise_progress(table: pd.DataFrame) -> str:
    """One-line plain-English summary above the progress grid."""
    if table.empty:
        return "_No cells yet — the grid populates as the sweep dispatches its first cell._"
    counts = table["status"].value_counts().to_dict()
    parts = [f"**{int(v)} {k}**" for k, v in counts.items()]
    return " · ".join(parts)


def _refresh_progress_grid() -> tuple[pd.DataFrame, str]:
    """Re-read the newest run's manifest + parquet for the progress grid.

    Returns ``(table_df, summary_markdown)``. There is no run-selector:
    the newest sweep is auto-discovered on every call. A mid-write
    manifest falls back to the last-good snapshot via the stale-data
    cache rather than blanking the grid.
    """
    manifest_path = _newest_manifest_path()
    if manifest_path is None:
        return _empty_progress_table(), _summarise_progress(_empty_progress_table())

    results_df = load_results_parquet(manifest_path.parent / "results.parquet")

    def _loader() -> pd.DataFrame:
        manifest = load_manifest(manifest_path)
        if not manifest:
            raise FileNotFoundError(f"manifest at {manifest_path} unreadable or empty")
        return build_progress_table(manifest, results_df=results_df)

    table, _warning = load_with_stale_fallback(
        _progress_cache,
        _loader,
        empty_factory=_empty_progress_table,
    )
    return table, _summarise_progress(table)


# --------------------------------------------------------------------- #
# Status tab -- top-of-screen sections (banner / KPIs / leaderboard /   #
# anomalies / resources)                                                #
# --------------------------------------------------------------------- #


def refresh_status() -> tuple[str, str, pd.DataFrame, str, pd.DataFrame, str, str]:
    """Recompute every Status section. Driven by the 5 s timer + load.

    Returns the 7-tuple
    ``(banner_html, kpi_html, progress_df, progress_summary_md,
    leaderboard_df, anomaly_html, resource_html)``.

    Reads the newest sweep run's manifest + parquet; every section
    degrades to an empty / neutral state when nothing is on disk yet
    rather than crashing the tick. The raw-log accordion has its own
    handler (it polls faster).
    """
    manifest_path = _newest_manifest_path()
    manifest: dict[str, Any] = {}
    results_path: Path | None = None
    if manifest_path is not None:
        manifest = load_manifest(manifest_path)
        results_path = manifest_path.parent / "results.parquet"

    throttle = read_throttle_state()
    kpis = compute_mission_kpis(manifest, throttled=bool(throttle.frozen))

    results_df = load_results_parquet(results_path)
    leaderboard = leaderboard_dataframe(build_live_leaderboard(results_df))
    anomalies = run_anomaly_review(results_path)

    progress_df, progress_summary = _refresh_progress_grid()

    return (
        _render_health_banner(kpis),
        _render_kpi_strip(kpis),
        progress_df,
        progress_summary,
        leaderboard,
        _render_anomaly_panel(anomalies),
        _render_resource_panel(throttle),
    )


# --------------------------------------------------------------------- #
# Status tab -- raw sweep log (folded accordion)                        #
# --------------------------------------------------------------------- #


def _newest_log_path() -> Path | None:
    """Return the newest ``sweep-*.log`` path, or ``None``.

    Like the manifest, the log is auto-discovered -- no selector. A
    sweep that starts after the dashboard is open is picked up on the
    next tick.
    """
    logs = discover_sweep_logs()
    return logs[0] if logs else None


def refresh_raw_log() -> tuple[str, str]:
    """Tail the newest sweep log; return ``(html_block, header_md)``.

    The raw log is the bottom-of-Status accordion -- folded by default.
    No filter / tail controls: an operator who has scrolled all the way
    down to the raw log wants the unfiltered tail. Empty / missing log
    yields an empty block plus a one-line hint.
    """
    log_path = _newest_log_path()
    if log_path is None:
        return "", (
            "_No sweep log found under_ "
            f"`{env_dashboard_logs_dir()}`. _The log appears once the sweep "
            "dispatches its first cell._"
        )
    lines = tail_log_lines(log_path, n=DEFAULT_LOG_TAIL_LINES)
    if not lines:
        return "", (
            f"_Log at_ `{log_path.name}` _is empty. It populates as the sweep "
            "dispatches its first cell._"
        )
    body = format_log_lines_html(lines, categories=None)
    counts = summarize_log(lines)
    header = (
        f"Last **{len(lines)}** line(s) of `{log_path.name}` — "
        f"**{counts['dispatch']}** dispatched · "
        f"**{counts['success']}** completed · "
        f"**{counts['error']}** errors · "
        f"**{counts['breach']}** breaches"
    )
    html_block = (
        '<pre style="white-space:pre-wrap;font-family:ui-monospace,monospace;'
        "font-size:12px;line-height:1.35;margin:0;padding:8px;"
        "background:rgba(0,0,0,0.03);border-radius:6px;max-height:420px;"
        f'overflow:auto">{body}</pre>'
        "<script>(()=>{const p=document.querySelectorAll('pre');"
        "if(p.length){const e=p[p.length-1];e.scrollTop=e.scrollHeight;}})();</script>"
    )
    return html_block, header


# --------------------------------------------------------------------- #
# Pre-flight tab (was: Calibration inspector)                           #
# --------------------------------------------------------------------- #


def refresh_calibration() -> tuple[pd.DataFrame, str]:
    """Find the latest calibration JSON and build its table.

    Returns ``(table_df, status_markdown)``. Status describes which
    file was read (path + cell count) so the operator can confirm
    they're inspecting the right run.
    """
    path = find_latest_calibration(env_dashboard_results_dir())
    if path is None:
        empty = pd.DataFrame({c: [] for c in CALIBRATION_COLUMNS})
        return empty, (
            "_No calibration JSON found under_ "
            f"`{env_dashboard_results_dir()}`. _Run_ `make calibrate` _first._"
        )

    report = load_calibration_report(path)
    if not report:
        empty = pd.DataFrame({c: [] for c in CALIBRATION_COLUMNS})
        return empty, f"_Could not read calibration JSON at_ `{path}`."

    table = build_calibration_table(report)
    n_cells = len(table)
    ts = report.get("timestamp_utc", "unknown")
    sha = report.get("git_sha", "unknown")[:8]
    return (
        table,
        (f"Reading **{path.name}** (timestamp `{ts}`, git `{sha}`); {n_cells} cell(s) in matrix."),
    )


# --------------------------------------------------------------------- #
# Rollouts tab                                                          #
# --------------------------------------------------------------------- #
#
# The "Best (cherry-pickable)" episode-selection mode was removed: an
# operator spot-checking a sweep does not need it, and the council
# flagged it as a foot-gun (it invites treating the best episode as
# typical). Only "Representative" (default) and "First" remain.

EPISODE_SELECT_RADIO_CHOICES: list[tuple[str, str]] = [
    ("Representative (default)", EPISODE_SELECT_REPRESENTATIVE),
    ("First", EPISODE_SELECT_FIRST),
]


def _latest_results_df() -> pd.DataFrame | None:
    """Load the per-episode parquet of the newest sweep run, if any."""
    manifest_path = _newest_manifest_path()
    if manifest_path is None:
        return None
    return load_results_parquet(manifest_path.parent / "results.parquet")


def _episode_options_for(
    index: Any,
    *,
    policy: str | None,
    env: str | None,
    seed: str | None,
) -> list[str]:
    """Episode values available on disk for one (policy, env, seed)."""
    if not policy or not env or seed in (None, ""):
        return []
    try:
        seed_int = int(seed)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return []
    eps = sorted(ep for (p, e, s, ep) in index.by_key if p == policy and e == env and s == seed_int)
    return [str(e) for e in eps]


def _default_episode_value(
    episodes: list[str],
    *,
    policy: str | None,
    env: str | None,
    seed: str | None,
    mode: str,
) -> str | None:
    """Resolve the default episode for the dropdown given the selection mode."""
    if not episodes:
        return None
    if not policy or not env or seed in (None, ""):
        return episodes[0]
    chosen = select_representative_episode(
        _latest_results_df(),
        policy=policy,
        env=env,
        seed=seed,
        mode=mode,
        available_episodes=[int(e) for e in episodes],
    )
    if chosen is None:
        return episodes[0]
    chosen_str = str(chosen)
    return chosen_str if chosen_str in episodes else episodes[0]


def _refresh_video_dropdowns(
    mode: str = EPISODE_SELECT_REPRESENTATIVE,
) -> tuple[Any, Any, Any, Any, str]:
    """Scan disk for videos and populate the four dropdowns.

    Returns ``(policy_update, env_update, seed_update, episode_update,
    status_markdown)``. The episode dropdown defaults to the
    *representative* episode of the first (policy, env, seed) on disk.
    """
    index = scan_video_index(DEFAULT_VIDEO_ROOTS)
    opts = video_index_options(index)

    def _first_or_none(values: list[str]) -> str | None:
        return values[0] if values else None

    policy = _first_or_none(opts["policy"])
    env = _first_or_none(opts["env"])
    seed = _first_or_none(opts["seed"])
    episodes = _episode_options_for(index, policy=policy, env=env, seed=seed)
    ep_value = _default_episode_value(episodes, policy=policy, env=env, seed=seed, mode=mode)

    status = _video_index_status(index)
    return (
        gr.update(choices=opts["policy"], value=policy),
        gr.update(choices=opts["env"], value=env),
        gr.update(choices=opts["seed"], value=seed),
        gr.update(choices=episodes or opts["episode"], value=ep_value),
        status,
    )


def _video_index_status(index: Any) -> str:
    roots = ", ".join(f"`{r}`" for r in index.roots)
    return f"Indexed **{index.n_videos}** MP4(s) across {roots}."


def _on_video_rescan(mode: str) -> tuple[Any, Any, Any, Any, str]:
    """Manual re-scan: clear the cache then repopulate dropdowns."""
    clear_video_cache()
    return _refresh_video_dropdowns(mode)


def _on_episode_mode_change(
    policy: str | None,
    env: str | None,
    seed: str | None,
    mode: str,
) -> Any:
    """Re-pick the episode value when the selection radio (or a cell) changes."""
    index = scan_video_index(DEFAULT_VIDEO_ROOTS)
    episodes = _episode_options_for(index, policy=policy, env=env, seed=seed)
    ep_value = _default_episode_value(episodes, policy=policy, env=env, seed=seed, mode=mode)
    return gr.update(choices=episodes, value=ep_value)


def _on_video_select(
    policy: str | None,
    env: str | None,
    seed: str | None,
    episode: str | None,
) -> tuple[Any, str]:
    """Look up the MP4 for the current dropdown combination.

    Returns ``(video_update, status_markdown)``. On miss returns a
    "no rollout for this combination" message so the page never
    crashes on a dropdown shuffle.
    """
    index = scan_video_index(DEFAULT_VIDEO_ROOTS)
    path = find_video_path(index, policy=policy, env=env, seed=seed, episode=episode)
    if path is None:
        return gr.update(value=None, visible=False), (
            f"_No rollout for `{policy}` / `{env}` / seed `{seed}` / ep `{episode}`._"
        )
    return gr.update(value=str(path), visible=True), f"Playing `{path.name}`."


# --------------------------------------------------------------------- #
# UI construction                                                       #
# --------------------------------------------------------------------- #


def _build_status_tab(demo: gr.Blocks) -> None:
    """Render the Status tab -- the default landing screen.

    One scrolling screen, auto-refreshing every 5 s: health banner,
    KPI strip, per-cell progress grid, live mini-leaderboard, anomaly
    alerts, resource/throttle panel, and a folded raw-log accordion.
    The health banner answers the 5-second test on first paint.
    """
    gr.Markdown(
        "_Leave this screen open while the sweep runs. "
        "It refreshes itself every 5 s — green means you can close "
        "the laptop, red means look._"
    )

    # 1. Health banner -- the 5-second-test sentence.
    banner = gr.HTML()

    # 2. KPI strip.
    kpi_strip = gr.HTML()

    # 3. Per-cell progress grid (newest run auto-loaded; no selector).
    gr.Markdown("### Per-cell progress")
    progress_summary = gr.Markdown("")
    progress_table = gr.Dataframe(
        headers=list(PROGRESS_COLUMNS),
        datatype=[
            "str",  # policy
            "str",  # env
            "str",  # status
            "number",  # seeds_done
            "number",  # seeds_total
            "number",  # episodes_done
            "number",  # episodes_total
            "str",  # success_rate_so_far
            "str",  # wilson_ci_so_far
            "str",  # seed_spread
            "str",  # last_update_utc
            "number",  # eta_minutes
        ],
        interactive=False,
        wrap=True,
        label="Per-(policy, env) cell status — newest sweep run",
    )
    with gr.Accordion("What the columns mean", open=False):
        gr.Markdown(column_glossary_markdown("progress"))

    # 4. Live results forming.
    gr.Markdown("### Live results forming")
    leaderboard = gr.Dataframe(
        headers=list(LEADERBOARD_COLUMNS),
        datatype=["str", "str", "str", "number", "number"],
        interactive=False,
        wrap=True,
        label="Per-policy mean success rate (Wilson 95% CI) across completed cells",
    )

    # 5. Anomaly alerts.
    gr.Markdown("### Anomaly alerts")
    anomaly_panel = gr.HTML()

    # 6. Resource + throttle.
    gr.Markdown("### Resource + throttle")
    resource_panel = gr.HTML()

    refresh_btn = gr.Button("Refresh now", variant="secondary")

    # 7. Raw sweep log -- folded, faster cadence, separate handler.
    with gr.Accordion("Raw sweep log", open=False):
        log_header = gr.Markdown("")
        log_view = gr.HTML(value="")

    status_outputs = [
        banner,
        kpi_strip,
        progress_table,
        progress_summary,
        leaderboard,
        anomaly_panel,
        resource_panel,
    ]

    demo.load(fn=refresh_status, inputs=None, outputs=status_outputs)
    demo.load(fn=refresh_raw_log, inputs=None, outputs=[log_view, log_header])
    refresh_btn.click(fn=refresh_status, inputs=None, outputs=status_outputs)
    refresh_btn.click(fn=refresh_raw_log, inputs=None, outputs=[log_view, log_header])

    status_timer = gr.Timer(value=STATUS_REFRESH_SECONDS)
    status_timer.tick(fn=refresh_status, inputs=None, outputs=status_outputs)

    log_timer = gr.Timer(value=LOG_REFRESH_SECONDS)
    log_timer.tick(fn=refresh_raw_log, inputs=None, outputs=[log_view, log_header])


def _build_preflight_tab(demo: gr.Blocks) -> None:
    """Render the Pre-flight tab -- the calibration inspector."""
    gr.Markdown(
        "**Pre-flight check.** Calibration runs *before* the sweep: it "
        "probes each `(policy, env)` cell for inference latency and peak "
        "VRAM, then auto-downscopes a cell's episode budget when it is "
        "too slow or VRAM-pressured. That is why a cell can show fewer "
        "than 50 episodes on the Status tab."
    )

    with gr.Accordion("More on what this tab shows", open=False):
        gr.Markdown(per_tab_intro_markdown("calibration"))

    status_md = gr.Markdown("")
    refresh_btn = gr.Button("Reload latest calibration", variant="secondary")
    cal_table = gr.Dataframe(
        headers=list(CALIBRATION_COLUMNS),
        datatype=[
            "str",  # policy
            "str",  # env
            "str",  # status
            "number",  # mean_step_ms
            "number",  # p95_step_ms
            "str",  # std_step_ms
            "number",  # n_steps
            "str",  # latency_skew
            "number",  # vram_peak_mb
            "number",  # recommended_seeds
            "number",  # recommended_episodes
            "str",  # reason
        ],
        interactive=False,
        wrap=True,
        label="Calibration cells (auto-downscope recommendations)",
    )
    gr.Markdown(column_glossary_markdown("calibration"))

    demo.load(fn=refresh_calibration, inputs=None, outputs=[cal_table, status_md])
    refresh_btn.click(fn=refresh_calibration, inputs=None, outputs=[cal_table, status_md])


def _build_rollouts_tab(demo: gr.Blocks) -> None:
    """Render the Rollouts tab.

    The episode dropdown defaults to the *representative* episode of
    the selected cell (modal outcome, step count closest to the cell
    median); the "Episode selection" radio lets the operator switch to
    the first episode instead. The cherry-pickable "Best" mode was
    removed -- the council flagged it as a foot-gun for spot-checking.
    """
    with gr.Accordion("What this tab shows", open=False):
        gr.Markdown(per_tab_intro_markdown("rollouts"))

    status_md = gr.Markdown("")
    with gr.Row():
        policy_dd = gr.Dropdown(choices=[], label="Policy", interactive=True)
        env_dd = gr.Dropdown(choices=[], label="Env", interactive=True)
        seed_dd = gr.Dropdown(choices=[], label="Seed", interactive=True)
        ep_dd = gr.Dropdown(choices=[], label="Episode", interactive=True)
    episode_mode = gr.Radio(
        choices=EPISODE_SELECT_RADIO_CHOICES,
        value=EPISODE_SELECT_REPRESENTATIVE,
        label="Episode selection",
        info=(
            "Representative = modal outcome, step count closest to the "
            "cell median. First = lowest episode index."
        ),
        interactive=True,
    )
    rescan_btn = gr.Button("Re-scan video disks", variant="secondary")
    video = gr.Video(
        label="Rollout",
        interactive=False,
        autoplay=False,
        visible=False,
    )

    demo.load(
        fn=lambda: _refresh_video_dropdowns(EPISODE_SELECT_REPRESENTATIVE),
        inputs=None,
        outputs=[policy_dd, env_dd, seed_dd, ep_dd, status_md],
    )

    rescan_btn.click(
        fn=_on_video_rescan,
        inputs=[episode_mode],
        outputs=[policy_dd, env_dd, seed_dd, ep_dd, status_md],
    )

    for dd in (policy_dd, env_dd, seed_dd):
        dd.change(
            fn=_on_episode_mode_change,
            inputs=[policy_dd, env_dd, seed_dd, episode_mode],
            outputs=[ep_dd],
        )

    episode_mode.change(
        fn=_on_episode_mode_change,
        inputs=[policy_dd, env_dd, seed_dd, episode_mode],
        outputs=[ep_dd],
    )

    for dd in (policy_dd, env_dd, seed_dd, ep_dd):
        dd.change(
            fn=_on_video_select,
            inputs=[policy_dd, env_dd, seed_dd, ep_dd],
            outputs=[video, status_md],
        )


def build_app() -> gr.Blocks:
    """Construct the Gradio Blocks app.

    Three tabs, Status first and default. A minimal title line sits
    above the tab strip; the resolved ``DASHBOARD_RESULTS_DIR`` /
    ``DASHBOARD_LOGS_DIR`` paths live in a folded "diagnostics"
    accordion -- visible if a misconfigured path needs checking, not
    shouting a wall of project pitch at the operator on every paint.
    """
    with gr.Blocks(
        title="lerobot-bench sweep dashboard",
        theme=gr.themes.Default(),
    ) as demo:
        gr.Markdown("# lerobot-bench — sweep dashboard")
        with gr.Accordion("Diagnostics", open=False):
            gr.Markdown(resolved_paths_banner_markdown())

        with gr.Tabs():
            with gr.Tab("Status", id=STATUS_TAB_ID):
                _build_status_tab(demo)
            with gr.Tab("Pre-flight", id=PREFLIGHT_TAB_ID):
                _build_preflight_tab(demo)
            with gr.Tab("Rollouts", id=ROLLOUTS_TAB_ID):
                _build_rollouts_tab(demo)

    return demo


# Built lazily inside ``__main__`` so import-time work stays minimal.
demo: gr.Blocks | None = None


if __name__ == "__main__":
    demo = build_app()
    demo.queue()
    # GRADIO_SERVER_NAME lets an operator bind to 0.0.0.0 for tablet
    # access over the tailnet; defaults to loopback.
    demo.launch(
        server_name=os.environ.get("GRADIO_SERVER_NAME", "127.0.0.1"),
        show_error=True,
    )
