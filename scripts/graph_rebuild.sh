#!/bin/sh
# graph_rebuild.sh — nightly vault maintenance. $0, AST-only, no LLM, never --mode deep.
#
# Steps (each fail-open — WARN + keep going, rc mirrored into health.json):
#   1. optional chat-transcript import (OFF by default, PERSONAL_OS_IMPORT_CHATS=1)
#   2. `graphify update <vault>` + [[wikilink]] edge injection (structure recall)
#   3. `qmd update && qmd embed` (semantic recall index)
#   4. fire-log rotation (drop recall records older than 180 days)
#   5. vault snapshot via vault_autopush.sh (allowlist commit + push — ONE code path
#      with the Stop hook; silent no-op if the vault has no git repo/remote)
#   6. runtime doctor (os_doctor.py, read-only)
#
# Hardening: mkdir lock against double runs; every step reports rc/duration to
# pos_health.py so failures are machine-readable instead of free text in a log
# nobody reads. Safe to run nightly (launchd on macOS, cron on Linux) — the
# installer registers this for you with --schedule.
#
# Config: PERSONAL_OS_VAULT (default ~/vault), PERSONAL_OS_SCRIPTS_DIR (where this
#         lives), PERSONAL_OS_LOG_DIR (debug log), PERSONAL_OS_HOME (state home).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")           # expand a leading ~
export PERSONAL_OS_VAULT="$VAULT"     # child scripts (import, autopush) see the expanded path
SCRIPTS_DIR="${PERSONAL_OS_SCRIPTS_DIR:-$(CDPATH= cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/graph-rebuild.log"
PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"; PO=$(eval echo "$PO")
export PERSONAL_OS_HOME="$PO"   # pos_health/pos_utils (called below) must see the same home
LOCKROOT="$PO/locks"
HEALTH_PY="$SCRIPTS_DIR/pos_health.py"

ts() { date '+%F %T'; }
health() { python3 "$HEALTH_PY" "$@" >/dev/null 2>&1 || true; }

# mkdir lock — mirror of pos_utils.acquire_lock (same lock directory).
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

# Watchdog: bound every step with a timeout where available. A hung `graphify update`
# (memory pressure) must not silently kill the WHOLE run — with a timeout the hang is
# cut, a WARN is logged, and the run continues (qmd + snapshot + doctor ALWAYS get
# their turn).
TIMEOUT_BIN=""
command -v timeout  >/dev/null 2>&1 && TIMEOUT_BIN=timeout
command -v gtimeout >/dev/null 2>&1 && TIMEOUT_BIN=gtimeout
run() {  # run <label> <seconds> <cmd...>
  label="$1"; secs="$2"; shift 2
  t0=$(date +%s)
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 30 "$secs" "$@" >> "$LOG" 2>&1; rc=$?
  else
    "$@" >> "$LOG" 2>&1; rc=$?
  fi
  health step graph "$label" "$rc" $(( $(date +%s) - t0 ))
  if [ "$rc" -eq 124 ]; then echo "[$(ts)] WARN: '$label' timed out after ${secs}s — skipped, run continues" >> "$LOG"
  elif [ "$rc" -ne 0 ]; then echo "[$(ts)] WARN: '$label' failed (rc=$rc)" >> "$LOG"; fi
  return 0
}

echo "[$(ts)] === graph rebuild start ===" >> "$LOG"
if [ ! -d "$VAULT" ]; then
  echo "[$(ts)] vault not found at $VAULT — skipping" >> "$LOG"
  exit 0
fi
if ! lock_acquire graph 360; then
  echo "[$(ts)] WARN: graph lock busy — another run is active, exiting" >> "$LOG"
  exit 0
fi
trap 'lock_release graph' EXIT
health begin graph

# (1) Optional, OFF by default: import Claude Code transcripts into the vault so
# `/mine-chats` has something to distill. This copies ALL your session transcripts
# into the vault — a privacy choice — so it only runs when you explicitly set
# PERSONAL_OS_IMPORT_CHATS=1. (chats/ is gitignored by the vault scaffold.)
if [ "${PERSONAL_OS_IMPORT_CHATS:-0}" = "1" ] && [ -f "$SCRIPTS_DIR/claude_to_obsidian.py" ]; then
  echo "[$(ts)] import chat transcripts" >> "$LOG"
  run "chat import" 600 python3 "$SCRIPTS_DIR/claude_to_obsidian.py"
fi

# (2) Knowledge graph (structure recall) — optional, skipped if graphify is absent
if command -v graphify >/dev/null 2>&1; then
  echo "[$(ts)] graphify update $VAULT" >> "$LOG"
  run "graphify update" 600 graphify update "$VAULT"
  if [ -f "$SCRIPTS_DIR/vault_inject_wikilinks.py" ]; then
    echo "[$(ts)] inject wikilinks" >> "$LOG"
    run "wikilink inject" 300 python3 "$SCRIPTS_DIR/vault_inject_wikilinks.py" "$VAULT"
  fi
else
  echo "[$(ts)] graphify not installed — graph steps skipped" >> "$LOG"
  health step graph "graphify update" 127 0
fi

# (3) qmd: semantic vault index (meaning search, complements graphify). $0 local,
# incremental (only changed notes). chats/ + _inbox/ deliberately excluded (index.yml).
if command -v qmd >/dev/null 2>&1; then
  echo "[$(ts)] qmd re-index" >> "$LOG"
  run "qmd update+embed" 900 sh -c 'qmd update >/dev/null 2>&1 && qmd embed >/dev/null 2>&1'
else
  echo "[$(ts)] WARN: qmd not found — semantic index skipped" >> "$LOG"
  health step graph "qmd update+embed" 127 0
fi

# (4) Hygiene: fire-log rotation (180d)
run "fire-log compact" 60 python3 -c "import sys; sys.path.insert(0, '$SCRIPTS_DIR'); import pos_utils; print('dropped:', pos_utils.fire_log_compact(180))"

# (5) Vault snapshot: daily commit + push to the private backup repo — via the
# hardened vault_autopush.sh (allowlist + lock + rc check). ONE code path instead
# of two diverging ones; silently no-ops if the vault is not a git repo.
run "vault autopush" 300 /bin/sh "$SCRIPTS_DIR/vault_autopush.sh" "nightly snapshot $(date '+%F')"

# (6) Self-health: run the runtime doctor ($0, read-only) and log it. Never breaks
# the rebuild; its verdict lands in health.json via pos_health doctor-record.
if [ -f "$PO/os_doctor.py" ]; then
  echo "[$(ts)] self-health (os_doctor)" >> "$LOG"
  run "doctor" 120 python3 "$PO/os_doctor.py"
fi

health finalize graph
echo "[$(ts)] === graph rebuild done ===" >> "$LOG"
exit 0
