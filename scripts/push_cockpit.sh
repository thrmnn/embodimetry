#!/usr/bin/env bash
# Build the cockpit stage and rsync it to the VPS.
# fleet_status.json is excluded both ways so a full push can never regress a
# newer orchestrator heartbeat; --chmod because a laptop-side umask 077 would
# otherwise 403 www-data silently.
set -euo pipefail
cd "$(dirname "$0")/.."
# systemd user PATH resolves python3 to the distro's 3.8; the builder needs
# the miniforge interpreter the hub has always been built with (3.12, pyyaml)
PYTHON="${PYTHON:-$HOME/miniforge3/bin/python3}"
DEST="${COCKPIT_DEST:-hetzner:/srv/cockpit/current/}"
"$PYTHON" scripts/build_project_hub.py
exec rsync -az --delete --delay-updates --exclude fleet_status.json \
  --chmod=D755,F644 _hub/_stage/ "$DEST"
