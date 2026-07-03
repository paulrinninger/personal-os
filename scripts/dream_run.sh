#!/bin/sh
# dream_run.sh — nightly "dreaming" pass: local-only consolidation, suggestions only.
#
# Runs dream.py's passes in order (cheapest/safest first), each writing its own resume
# state, then assembles whatever fired into one dream note under
# <vault>/_inbox/dreams/. Never edits a live note. Safe to run nightly (launchd on
# macOS, systemd-timer/cron on Linux) — the installer can register this for you
# alongside graph_rebuild.sh, one hour or so later so the graph is fresh first.
#
# Kill switch: create a file named `dream.off` in PERSONAL_OS_HOME (default
# ~/.claude/personal-os) — remove it to turn dreaming back on.
#
# Config: PERSONAL_OS_VAULT, PERSONAL_OS_SCRIPTS_DIR, PERSONAL_OS_LOG_DIR,
#         PERSONAL_OS_HOME, PERSONAL_OS_OLLAMA, PERSONAL_OS_EMBED_MODEL,
#         PERSONAL_OS_DREAM_MODEL (defaults: see dream.py --help).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")
SCRIPTS_DIR="${PERSONAL_OS_SCRIPTS_DIR:-$(CDPATH= cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/dream.log"
PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"; PO=$(eval echo "$PO")
OLLAMA_BASE="${PERSONAL_OS_OLLAMA:-http://localhost:11434}"

ts() { date '+%F %T'; }
DREAM="python3 $SCRIPTS_DIR/dream.py"

# Best-effort timeout wrapper: this calls a local LLM, which occasionally hangs.
# Falls back to running unwrapped if neither timeout nor gtimeout is available —
# worst case the run takes longer, nothing is corrupted (every pass is resumable).
TIMEOUT_BIN=""
command -v timeout  >/dev/null 2>&1 && TIMEOUT_BIN=timeout
command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN=gtimeout
run() {  # run <label> <seconds> <cmd...>
  label="$1"; secs="$2"; shift 2
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 15 "$secs" "$@" >> "$LOG" 2>&1; rc=$?
  else
    "$@" >> "$LOG" 2>&1; rc=$?
  fi
  if [ "$rc" -eq 124 ]; then echo "[$(ts)] WARN: '$label' timed out after ${secs}s — skipped, run continues" >> "$LOG"
  elif [ "$rc" -ne 0 ]; then echo "[$(ts)] WARN: '$label' failed (rc=$rc)" >> "$LOG"; fi
  return 0
}

echo "[$(ts)] === dream run start ===" >> "$LOG"

if [ -f "$PO/dream.off" ]; then
  echo "[$(ts)] dream.off present — dreaming disabled, exiting" >> "$LOG"
  exit 0
fi

if [ ! -d "$VAULT" ]; then
  echo "[$(ts)] vault not found at $VAULT — skipping" >> "$LOG"
  exit 0
fi

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

run "fires"       60  $DREAM fires
if [ -z "${SKIP_LLM:-}" ]; then
  run "gc-digest" 300  $DREAM gc-digest
fi
run "connections" 600 $DREAM connections
if [ -z "${SKIP_LLM:-}" ]; then
  run "triage"    600  $DREAM triage
  run "residue"   900  $DREAM residue
fi
run "report"       60 $DREAM report

command -v ollama >/dev/null 2>&1 && {
  ollama stop "${PERSONAL_OS_DREAM_MODEL:-llama3.2:3b}" >/dev/null 2>&1
  ollama stop "${PERSONAL_OS_EMBED_MODEL:-nomic-embed-text}" >/dev/null 2>&1
}

echo "[$(ts)] === dream run done ===" >> "$LOG"
exit 0
