#!/bin/sh
# Stop-hook for Personal OS — fail-open, $0, fully local. Two DECOUPLED jobs:
#  (1) Auto-harvest enqueue: ANY substantive session (an Edit/Write/Bash/NotebookEdit action) that
#      ended WITHOUT /save → a breadcrumb in the harvest queue, processed later and INTERACTIVELY via
#      /harvest. Size-independent, so small fix-sessions are caught too (a >300KB gate would miss them).
#  (2) Save-nudge: only on LARGE (>300KB) un-saved sessions, remind once toward /save.
#
# Config: PERSONAL_OS_HOME (harvest queue), PERSONAL_OS_VAULT, PERSONAL_OS_LOG_DIR, PERSONAL_OS_LANG.
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

# Already wrote a vault log this session? PRECISE: a real file_path WRITE to a vault logs/*.md, NOT a
# mere mention of a logs/ path (CLAUDE.md / recall context / the /save doc would match a loose grep and
# wrongly suppress nudge+enqueue). Covers fallback (vault/logs/) AND project (vault/<project>/logs/).
# If saved → /save already harvested this session, so do neither enqueue nor nudge.
VB=$(basename "${PERSONAL_OS_VAULT:-$HOME/vault}")
grep -qE "\"file_path\":\"[^\"]*${VB}/([^\"]*/)?logs/[^\"]*\.md\"" "$TP" 2>/dev/null && exit 0

# (1) ENQUEUE — substantive = at least one Edit/Write/Bash/NotebookEdit action (not a pure read/research
#     chat). Size-independent. Once-per-session via EMARK; also deduped by session_id in the queue.
EMARK="${TMPDIR:-/tmp}/personal-os-harvest-enq-$SID"
if [ ! -f "$EMARK" ] && grep -qE '"name":"(Edit|Write|Bash|NotebookEdit)"' "$TP" 2>/dev/null; then
  PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"
  PO=$(eval echo "$PO")
  mkdir -p "$PO" 2>/dev/null
  QUEUE="$PO/harvest-queue.jsonl"
  if ! grep -q "\"$SID\"" "$QUEUE" 2>/dev/null; then
    printf '%s' "$IN" | "$JQ" -c '{session_id, transcript_path, cwd, ts: (now|todate)}' >> "$QUEUE" 2>/dev/null
  fi
  touch "$EMARK" 2>/dev/null
fi

# (2) NUDGE — only a large session (>300KB), once per session via MARK.
MARK="${TMPDIR:-/tmp}/personal-os-save-nudge-$SID"
if [ ! -f "$MARK" ]; then
  # Cross-platform file size: BSD/macOS `stat -f%z` vs GNU/Linux `stat -c%s`.
  SIZE=$(stat -f%z "$TP" 2>/dev/null || stat -c%s "$TP" 2>/dev/null || echo 0)
  if [ "$SIZE" -gt 300000 ] 2>/dev/null; then
    touch "$MARK" 2>/dev/null
    case "${PERSONAL_OS_LANG:-en}" in
      de*) MSG="💾 Personal OS: lange Session ohne /save — jetzt /save (Log + Lessons + Ideen) oder später /harvest.";;
      *)   MSG="💾 Personal OS: long session without /save — run /save (log + lessons + ideas) now, or /harvest later.";;
    esac
    printf '{"systemMessage":"%s"}\n' "$MSG"
  fi
fi
exit 0
