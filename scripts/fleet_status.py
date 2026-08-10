"""Single-writer helper for the cockpit's fleet heartbeat.

Only the orchestrator session writes `_hub/fleet_status.json` (subagents report
up through it, so no locking). Every write is atomic (tmp + os.replace) and is
rsynced straight to the VPS — the full cockpit push excludes this file, so a
rebuild can never regress a newer heartbeat. Never committed: `_hub/` is
gitignored and the repo is public.

    python scripts/fleet_status.py            # heartbeat: refresh generated_at + push
    python scripts/fleet_status.py --no-push  # local write only

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
        subprocess.run(["rsync", "-az", "--chmod=F644", str(STATUS), REMOTE], check=False)


if __name__ == "__main__":
    save(load(), push="--no-push" not in sys.argv)
