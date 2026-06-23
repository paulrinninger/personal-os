#!/bin/sh
# Stop-Hook "save-nudge" for Personal OS — fail-open, $0, fully local.
# Nudges ONCE per session toward /save when the transcript is large (>300KB)
# and no vault log has been written in this session yet.
#
# Config: PERSONAL_OS_LOG_DIR (debug log), PERSONAL_OS_LANG (en|de).
IN=$(cat 2>/dev/null) || exit 0

# jq is required for the Stop hook; degrade silently if absent.
JQ=$(command -v jq) || exit 0
SID=$(printf '%s' "$IN" | "$JQ" -r '.session_id // empty' 2>/dev/null) || exit 0
TP=$(printf '%s' "$IN" | "$JQ" -r '.transcript_path // empty' 2>/dev/null) || exit 0

# Resolve debug log dir (XDG by default; mac-friendly).
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/hooks.log"
echo "[$(date '+%F %T')] stop-hook fired sid=${SID:-none} tp=$([ -n "$TP" ] && [ -f "$TP" ] && echo ok || echo missing)" >> "$LOG" 2>/dev/null

[ -n "$SID" ] && [ -n "$TP" ] && [ -f "$TP" ] || exit 0
MARK="${TMPDIR:-/tmp}/personal-os-save-nudge-$SID"
[ -f "$MARK" ] && exit 0

# Cross-platform file size: BSD/macOS `stat -f%z` vs GNU/Linux `stat -c%s`.
SIZE=$(stat -f%z "$TP" 2>/dev/null || stat -c%s "$TP" 2>/dev/null || echo 0)
[ "$SIZE" -gt 300000 ] 2>/dev/null || exit 0

# Already wrote/updated a vault log this session? (path pattern in transcript).
# Match the configured vault's folder name, not a hardcoded "vault".
VB=$(basename "${PERSONAL_OS_VAULT:-$HOME/vault}")
grep -q "$VB/[^\"]*logs/" "$TP" 2>/dev/null && exit 0
touch "$MARK" 2>/dev/null

case "${PERSONAL_OS_LANG:-en}" in
  de*) MSG="💾 Personal OS: Lange Session ohne /save — jetzt sichern lohnt sich (Log + Lessons + Ideen in den Vault).";;
  *)   MSG="💾 Personal OS: long session without /save — a checkpoint now is worth it (log + lessons + ideas into your vault).";;
esac
printf '{"systemMessage":"%s"}\n' "$MSG"
exit 0
