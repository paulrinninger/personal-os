#!/bin/sh
# dream_run.sh — nightly "dreaming" pass: local-only consolidation + silent autopilot.
#
# Runs dream.py's passes in order (cheapest/safest first), each writing its own resume
# state, then lets pos_autopilot.py EXECUTE the low-risk layer (every action journaled
# with verbatim undo data — /undo rolls a whole night back), and finally assembles the
# night journal under <vault>/_inbox/dreams/. Safe to run nightly (launchd on macOS,
# systemd-timer/cron on Linux) — the installer registers this for you with
# --schedule-dream, ~30 minutes after graph_rebuild.sh so the graph is fresh first.
#
# Kill switches (files in PERSONAL_OS_HOME, default ~/.claude/personal-os):
#   dream.off      — everything off (passes + autopilot)
#   autopilot.off  — execution off, passes keep running (checked by pos_autopilot.py)
#
# Hardening:
#  - mkdir lock (mirror of pos_utils.acquire_lock, SAME lock directory) so a nightly
#    run and a manual test run never race each other.
#  - every pass reports rc/duration to pos_health.py (health.json) — fail-open
#    semantics stay: WARN + keep going, but failures are machine-readable and
#    surfaced once per day. Early exits (kill switch, RAM) finalize too, so the
#    health file never claims a run is still in flight.
#
# Config: PERSONAL_OS_VAULT, PERSONAL_OS_SCRIPTS_DIR, PERSONAL_OS_LOG_DIR,
#         PERSONAL_OS_HOME, PERSONAL_OS_OLLAMA, PERSONAL_OS_EMBED_MODEL,
#         PERSONAL_OS_DREAM_MODEL (defaults: see dream.py --help).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")
export PERSONAL_OS_VAULT="$VAULT"   # dream.py sees the expanded path
SCRIPTS_DIR="${PERSONAL_OS_SCRIPTS_DIR:-$(CDPATH= cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/dream.log"
PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"; PO=$(eval echo "$PO")
export PERSONAL_OS_HOME="$PO"   # pos_health/pos_utils (called below) must see the same home
LOCKROOT="$PO/locks"
HEALTH_PY="$SCRIPTS_DIR/pos_health.py"
OLLAMA_BASE="${PERSONAL_OS_OLLAMA:-http://localhost:11434}"

ts() { date '+%F %T'; }
health() { python3 "$HEALTH_PY" "$@" >/dev/null 2>&1 || true; }

# mkdir lock — mirror of pos_utils.acquire_lock (same lock directory, so the Python
# side and this shell side contend correctly).
lock_acquire() {  # lock_acquire <name> <stale_minutes>
  _d="$LOCKROOT/$1.lock.d"; _stale="${2:-360}"
  mkdir -p "$LOCKROOT" 2>/dev/null
  if mkdir "$_d" 2>/dev/null; then echo $$ > "$_d/pid" 2>/dev/null; return 0; fi
  if [ -n "$(find "$_d" -maxdepth 0 -mmin +"$_stale" 2>/dev/null)" ] || \
     { [ -f "$_d/pid" ] && ! kill -0 "$(cat "$_d/pid" 2>/dev/null)" 2>/dev/null; }; then
    rm -rf "$_d" 2>/dev/null
    if mkdir "$_d" 2>/dev/null; then echo $$ > "$_d/pid" 2>/dev/null; return 0; fi
  fi
  return 1
}
lock_release() { rm -rf "$LOCKROOT/$1.lock.d" 2>/dev/null; }

# Best-effort timeout wrapper: this calls a local LLM, which occasionally hangs.
# Falls back to running unwrapped if neither timeout nor gtimeout is available —
# worst case the run takes longer, nothing is corrupted (every pass is resumable).
TIMEOUT_BIN=""
command -v timeout  >/dev/null 2>&1 && TIMEOUT_BIN=timeout
command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN=gtimeout
run() {  # run <label> <seconds> <cmd...>
  label="$1"; secs="$2"; shift 2
  t0=$(date +%s)
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 15 "$secs" "$@" >> "$LOG" 2>&1; rc=$?
  else
    "$@" >> "$LOG" 2>&1; rc=$?
  fi
  health step dream "$label" "$rc" $(( $(date +%s) - t0 ))
  if [ "$rc" -eq 124 ]; then echo "[$(ts)] WARN: '$label' timed out after ${secs}s — skipped, run continues" >> "$LOG"
  elif [ "$rc" -ne 0 ]; then echo "[$(ts)] WARN: '$label' failed (rc=$rc)" >> "$LOG"; fi
  return 0
}

echo "[$(ts)] === dream run start ===" >> "$LOG"

if [ -f "$PO/dream.off" ]; then
  echo "[$(ts)] dream.off present — dreaming disabled, exiting" >> "$LOG"
  health begin dream
  health step dream "kill-switch (deliberately off)" 0 0
  health finalize dream
  exit 0
fi

if [ ! -d "$VAULT" ]; then
  echo "[$(ts)] vault not found at $VAULT — skipping" >> "$LOG"
  health begin dream
  health step dream "vault missing" 1 0
  health finalize dream
  exit 0
fi

if ! lock_acquire dream 360; then
  echo "[$(ts)] WARN: dream lock busy — another run is active, exiting" >> "$LOG"
  exit 0
fi
trap 'lock_release dream' EXIT
health begin dream

# Collision guard: wait (up to 20 min) if the graph rebuild is still running, so
# dreaming works off a freshly-indexed vault; if it's still going after that, run
# the LLM-free passes only.
waited=0
while pgrep -f graph_rebuild.sh >/dev/null 2>&1; do
  if [ "$waited" -ge 1200 ]; then
    echo "[$(ts)] WARN: graph_rebuild still running after 20min — running LLM-free passes only" >> "$LOG"
    SKIP_LLM=1
    break
  fi
  sleep 60; waited=$((waited + 60))
done

# RAM pre-flight, best-effort per platform. DREAM_PREFLIGHT_OVERRIDE=1 forces a full
# run (useful for testing during the day). Unrecognized platform -> assume it's fine.
LVL=1; FREE=100
if [ -z "${DREAM_PREFLIGHT_OVERRIDE:-}" ]; then
  if command -v sysctl >/dev/null 2>&1 && sysctl kern.memorystatus_vm_pressure_level >/dev/null 2>&1; then
    LVL=$(sysctl -n kern.memorystatus_vm_pressure_level 2>/dev/null || echo 1)
    FREE=$(memory_pressure 2>/dev/null | awk -F': ' '/free percentage/{gsub("%","",$2); print int($2)}')
    FREE=${FREE:-100}
  elif [ -r /proc/meminfo ]; then
    FREE=$(awk '/MemAvailable/{a=$2} /MemTotal/{t=$2} END{if(t>0) print int(a*100/t); else print 100}' /proc/meminfo)
    [ "$FREE" -lt 25 ] && LVL=2
  fi
  echo "[$(ts)] pre-flight: pressure-level=$LVL free=${FREE}%" >> "$LOG"
  if [ "$LVL" -ge 4 ]; then
    echo "[$(ts)] memory critical — skipping this run entirely" >> "$LOG"
    health step dream "ram-preflight (full skip)" 0 0
    health finalize dream
    exit 0
  elif [ "$LVL" -ge 2 ] || [ "$FREE" -lt 25 ]; then
    echo "[$(ts)] memory tight — running LLM-free passes only" >> "$LOG"
    SKIP_LLM=1
  fi
fi

# curl -f 2>/dev/null || true so this never trips `set -u`'s undefined-var strictness
# on the exit code path; the ollama-reachability check itself lives in dream.py.
OLLAMA_OK=0
if command -v curl >/dev/null 2>&1 && curl -sf -m 2 "$OLLAMA_BASE/api/version" >/dev/null 2>&1; then
  OLLAMA_OK=1
fi
[ "$OLLAMA_OK" = 0 ] && SKIP_LLM=1

# Implicit feedback collector FIRST (scores the previous nights' autopilot actions —
# feeds adaptive_params before tonight's passes pull their thresholds).
run "collect-feedback" 60 python3 "$SCRIPTS_DIR/pos_actions.py" collect-feedback

# Passes strictly sequential (cheapest first; each resumes via its pass JSON).
# dream.py is invoked quoted — an unquoted command string would word-split on a
# scripts dir containing spaces.
run "fires"       60  python3 "$SCRIPTS_DIR/dream.py" fires
# producer: pure templating, no ollama call in the core pass -> always runs, even SKIP_LLM
run "producer"    120 python3 "$SCRIPTS_DIR/dream.py" producer
run "connections" 600 python3 "$SCRIPTS_DIR/dream.py" connections
if [ -z "${SKIP_LLM:-}" ]; then
  run "gc-digest" 300  python3 "$SCRIPTS_DIR/dream.py" gc-digest
  # ventures uses nomic-embed (like triage) -> skipped under RAM pressure/collision too,
  # not just on a real ollama outage (cmd_ventures itself checks ollama_up() as well)
  run "ventures"  180  python3 "$SCRIPTS_DIR/dream.py" ventures
  run "triage"    600  python3 "$SCRIPTS_DIR/dream.py" triage
  run "residue"   900  python3 "$SCRIPTS_DIR/dream.py" residue
fi

# AUTOPILOT: EXECUTE the low-risk layer (journaled via pos_actions.py, `/undo` rolls a
# whole night back). Own kill switch: `autopilot.off` in PERSONAL_OS_HOME (checked by
# pos_autopilot.py itself — the passes above keep running, only execution stops).
# act-links/act-dreams need no model; act-refs needs ollama (skips itself);
# act-mine/act-harvest are LLM stages -> under the SKIP_LLM guard.
run "act-links"    120 python3 "$SCRIPTS_DIR/pos_autopilot.py" act-links
run "act-dreams"    60 python3 "$SCRIPTS_DIR/pos_autopilot.py" act-dreams
run "act-refs"     600 python3 "$SCRIPTS_DIR/pos_autopilot.py" act-refs
if [ -z "${SKIP_LLM:-}" ]; then
  run "act-mine"    900 python3 "$SCRIPTS_DIR/pos_autopilot.py" act-mine
  run "act-harvest" 900 python3 "$SCRIPTS_DIR/pos_autopilot.py" act-harvest
fi

run "report"       60 python3 "$SCRIPTS_DIR/dream.py" report
run "notify"       30 python3 "$SCRIPTS_DIR/pos_autopilot.py" notify

# Belt-and-braces: unload the models (keep_alive windows are short, but explicit is explicit).
command -v ollama >/dev/null 2>&1 && {
  ollama stop "${PERSONAL_OS_DREAM_MODEL:-llama3.2:3b}" >/dev/null 2>&1
  ollama stop "${PERSONAL_OS_EMBED_MODEL:-nomic-embed-text}" >/dev/null 2>&1
}

health finalize dream
echo "[$(ts)] === dream run done ===" >> "$LOG"
exit 0
