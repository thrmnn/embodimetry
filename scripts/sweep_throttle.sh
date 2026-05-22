#!/usr/bin/env bash
# Active throttle + progress monitor for the overnight sweep.
#
# Beyond passive alerting, this *acts*: when system-wide free RAM drops
# below the comfort margin it FREEZES the sweep's cgroup (cgroup v2
# cgroup.freeze) so the sweep stops competing for memory and CPU; it
# THAWS again once RAM recovers (hysteresis to avoid flapping). The
# sweep keeps low CPU/IO priority at all times (renice +10, ionice idle).
#
# Freeze is fully reversible and loses nothing — the in-flight cell is
# suspended, not killed, and resumes exactly where it stopped.
#
# Emits one line per actionable event (freeze, thaw, cell ok/fail,
# long-freeze warning, sweep exit) — silent while healthy.
#
# Env overrides:
#   FREEZE_BELOW_GB  free-RAM floor that triggers a freeze (default 5)
#   THAW_ABOVE_GB    free-RAM level that triggers a thaw   (default 8)
#   SAMPLE_S         sample interval seconds               (default 15)

set -u

FREEZE_BELOW_GB="${FREEZE_BELOW_GB:-5}"
THAW_ABOVE_GB="${THAW_ABOVE_GB:-8}"
SAMPLE_S="${SAMPLE_S:-15}"

LOG=$(cat /tmp/lerobot-bench-sweep-log 2>/dev/null)
state="running"          # running | frozen
frozen_since=0
last_line=$(wc -l < "$LOG" 2>/dev/null || echo 0)

echo "$(date +%H:%M:%S) throttle armed — freeze<${FREEZE_BELOW_GB}GB thaw>${THAW_ABOVE_GB}GB, sweep niced+ionice-idle"

freeze_path() {
  # Re-discover each call so a sweep relaunch (new scope) is handled.
  local pid cg
  pid=$(pgrep -f "run_sweep.py" | head -1) || return 1
  [ -n "$pid" ] || return 1
  cg=$(awk -F: '{print $3}' "/proc/$pid/cgroup" 2>/dev/null | head -1)
  [ -n "$cg" ] || return 1
  echo "/sys/fs/cgroup${cg}/cgroup.freeze"
}

while true; do
  # --- sweep alive? ---
  if ! pgrep -f "run_sweep.py" >/dev/null 2>&1; then
    echo "$(date +%H:%M:%S) ⏹ sweep process gone — throttle exiting"
    tail -n 3 "$LOG" 2>/dev/null
    exit 0
  fi

  avail_kb=$(awk '/MemAvailable/{print $2}' /proc/meminfo)
  avail_gb=$(( avail_kb / 1048576 ))
  fz=$(freeze_path)

  # --- throttle state machine (hysteresis) ---
  if [ "$state" = "running" ]; then
    if [ "$avail_gb" -lt "$FREEZE_BELOW_GB" ] && [ -n "$fz" ] && [ -w "$fz" ]; then
      echo 1 > "$fz" 2>/dev/null \
        && { state="frozen"; frozen_since=$(date +%s);
             echo "$(date +%H:%M:%S) ❄️  FROZE sweep — free RAM ${avail_gb}GB < ${FREEZE_BELOW_GB}GB; yielding to other apps"; }
    fi
  else  # frozen
    if [ "$avail_gb" -gt "$THAW_ABOVE_GB" ] && [ -n "$fz" ] && [ -w "$fz" ]; then
      echo 0 > "$fz" 2>/dev/null \
        && { held=$(( $(date +%s) - frozen_since ));
             state="running";
             echo "$(date +%H:%M:%S) ☀️  THAWED sweep — free RAM ${avail_gb}GB > ${THAW_ABOVE_GB}GB (was frozen ${held}s)"; }
    else
      held=$(( $(date +%s) - frozen_since ))
      # Warn once if a freeze runs long — risks the 4h per-cell timeout.
      if [ "$held" -gt 1800 ] && [ $(( held % 1800 )) -lt "$SAMPLE_S" ]; then
        echo "$(date +%H:%M:%S) ⚠️  sweep frozen ${held}s (free RAM ${avail_gb}GB) — still waiting for >${THAW_ABOVE_GB}GB"
      fi
    fi
  fi

  # --- keep the sweep low-priority (new run_one children each cell) ---
  if [ -n "$fz" ]; then
    cgdir=$(dirname "$fz")
    for p in $(cat "$cgdir/cgroup.procs" 2>/dev/null); do
      renice +10 -p "$p" >/dev/null 2>&1
      ionice -c 3 -p "$p" 2>/dev/null
    done
  fi

  # --- progress events (only while running) ---
  if [ "$state" = "running" ] && [ -f "$LOG" ]; then
    cur=$(wc -l < "$LOG")
    if [ "$cur" -gt "$last_line" ]; then
      tail -n +"$((last_line+1))" "$LOG" \
        | grep -E "/107\] dispatch|-> ok|-> FAILED|exit=-[0-9]|BREACH|sweep complete" || true
      last_line=$cur
    fi
  fi

  sleep "$SAMPLE_S"
done
