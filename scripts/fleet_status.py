"""Single-writer helper for the cockpit's fleet heartbeat.

Only the orchestrator session writes `_hub/fleet_status.json` (subagents report
up through it, so no locking). Every write is atomic (tmp + os.replace) and is
rsynced straight to the VPS — the full cockpit push excludes this file, so a
rebuild can never regress a newer heartbeat. Never committed: `_hub/` is
gitignored and the repo is public.

    python scripts/fleet_status.py            # heartbeat: refresh generated_at + push
    python scripts/fleet_status.py --no-push  # local write only

Report a milestone via `add_milestone(status, track_id, text, link=None)` —
it bumps the track's `last_event_at` for you; never append to `milestones`
by hand.

Schema v1 keys: schema, generated_at, heartbeat_interval_s, orchestrator,
dashboard_up, git_sha, needs_theo[], sweeps[], tracks[] (id, title, state,
now, last_event_at, gates[], milestones[] capped at 10, pr?).
"""

from __future__ import annotations

import contextlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATUS = REPO / "_hub" / "fleet_status.json"
REMOTE = "hetzner:/srv/cockpit/current/fleet_status.json"


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def load() -> dict:
    if STATUS.exists():
        return json.loads(STATUS.read_text())
    return {"schema": 1, "heartbeat_interval_s": 10800, "tracks": []}


def save(status: dict, *, push: bool = True) -> None:
    status["schema"] = 1
    status["generated_at"] = now()
    status.setdefault("heartbeat_interval_s", 10800)
    with contextlib.suppress(Exception):
        status["git_sha"] = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO).decode().strip()
        )
    for track in status.get("tracks", []):
        track["milestones"] = track.get("milestones", [])[-10:]
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATUS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(status, indent=1, ensure_ascii=False) + "\n")
    os.replace(tmp, STATUS)
    if push:
        # check=True: a silent rsync failure means the cockpit keeps showing a
        # stale heartbeat while everything looks green from the laptop.
        subprocess.run(["rsync", "-az", "--chmod=F644", str(STATUS), REMOTE], check=True)


def add_milestone(status: dict, track_id: str, text: str, link: str | None = None) -> dict:
    """Append a milestone to a track and bump its last_event_at in one step.

    The bump lives here, not as a caller convention — a milestone without a
    matching last_event_at renders as a track that looks idle while its
    milestone list grows.
    """
    ts = now()
    for track in status.get("tracks", []):
        if track.get("id") == track_id:
            milestone = {"ts": ts, "text": text}
            if link:
                milestone["link"] = link
            track.setdefault("milestones", []).append(milestone)
            track["last_event_at"] = ts
            return milestone
    raise KeyError(f"no track with id {track_id!r} in fleet status")


if __name__ == "__main__":
    save(load(), push="--no-push" not in sys.argv)
