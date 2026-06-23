#!/bin/sh
# graph_rebuild.sh — rebuild the vault knowledge graph. $0, AST-only, no LLM.
#
# 1. `graphify update <vault>`  (lexical/AST extraction — never --mode deep, never an API key)
# 2. inject [[wikilink]] edges so `graphify query/path` can traverse the note network
#
# Safe to run nightly (launchd on macOS, systemd-timer/cron on Linux). The installer
# can register this for you. Does NOT commit or push anything.
#
# Config: PERSONAL_OS_VAULT (default ~/vault), PERSONAL_OS_SCRIPTS_DIR (where this lives),
#         PERSONAL_OS_LOG_DIR (debug log).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")           # expand a leading ~
SCRIPTS_DIR="${PERSONAL_OS_SCRIPTS_DIR:-$(CDPATH= cd "$(dirname "$0")" && pwd)}"
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/graph-rebuild.log"

ts() { date '+%F %T'; }

if ! command -v graphify >/dev/null 2>&1; then
  echo "[$(ts)] graphify not installed — skipping graph rebuild" >> "$LOG"
  exit 0
fi
if [ ! -d "$VAULT" ]; then
  echo "[$(ts)] vault not found at $VAULT — skipping" >> "$LOG"
  exit 0
fi

# Optional, OFF by default: import Claude Code transcripts into the vault so
# `/mine-chats` has something to distill. This copies ALL your session
# transcripts into the vault — a privacy choice — so it only runs when you
# explicitly set PERSONAL_OS_IMPORT_CHATS=1.
if [ "${PERSONAL_OS_IMPORT_CHATS:-0}" = "1" ] && [ -f "$SCRIPTS_DIR/claude_to_obsidian.py" ]; then
  echo "[$(ts)] import chat transcripts" >> "$LOG"
  PERSONAL_OS_VAULT="$VAULT" python3 "$SCRIPTS_DIR/claude_to_obsidian.py" >> "$LOG" 2>&1
fi

echo "[$(ts)] graphify update $VAULT" >> "$LOG"
graphify update "$VAULT" >> "$LOG" 2>&1

if [ -f "$SCRIPTS_DIR/vault_inject_wikilinks.py" ]; then
  echo "[$(ts)] inject wikilinks" >> "$LOG"
  python3 "$SCRIPTS_DIR/vault_inject_wikilinks.py" "$VAULT" >> "$LOG" 2>&1
fi

echo "[$(ts)] done" >> "$LOG"
exit 0
