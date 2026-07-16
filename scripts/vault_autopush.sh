#!/bin/sh
# vault_autopush.sh — commit + push pending vault changes to its (private) remote.
#
# Runs as an OPT-IN Stop hook (end of every Claude Code session, --autopush at install
# time) AND from the nightly graph_rebuild.sh — ONE code path for both. Fails open:
# never blocks or errors out a session.
#
# Hardening (why this is not `git add -A`):
#  - ALLOWLIST staging instead of `git add -A`: only curated folders + top-level *.md
#    get staged. A denylist (.gitignore) fails OPEN on every NEW sensitive folder —
#    the allowlist fails CLOSED. Raw chat transcripts have leaked into a remote via
#    add -A before; the allowlist makes that structurally impossible.
#  - Belt-and-braces: abort if anything from chats/ or _inbox/ lands in the index anyway.
#  - mkdir lock (mirror of pos_utils.acquire_lock, SAME lock directory): parallel
#    Stop hooks / the nightly run no longer race each other.
#  - git commit rc is checked (never push a failed state); untracked files outside
#    the allowlist are logged as WARN — fail-closed, never silent.
#
# Requires the vault to already be a git repo with a remote configured
# (`git -C <vault> remote add origin <url>`) — if not, this is a silent no-op.
#
# Usage: vault_autopush.sh [commit-message]   (default: "auto-sync <ts>")
# Config: PERSONAL_OS_VAULT (default ~/vault), PERSONAL_OS_HOME (lock dir),
#         PERSONAL_OS_LOG_DIR (debug log).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/hooks.log"
PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"; PO=$(eval echo "$PO")
LOCKROOT="$PO/locks"
MSG="${1:-auto-sync $(date '+%F %T')}"
# Curated allowlist: only these folders (plus top-level *.md) are ever staged.
ALLOW="lessons knowledge ideas projects profile permanent logs _templates _archive"

ts() { date '+%F %T'; }

lock_acquire() {  # lock_acquire <name> <stale_minutes> — mirror of pos_utils.acquire_lock
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

[ -d "$VAULT/.git" ] || exit 0

{
  cd "$VAULT" || exit 0
  if ! lock_acquire vault-git 30; then
    echo "[$(ts)] vault-autopush: lock busy — skip (another sync is running)"
    exit 0
  fi
  trap 'lock_release vault-git' EXIT

  # 1) Stage: ONLY allowlisted folders + top-level markdown
  for p in $ALLOW; do
    [ -e "$p" ] && git add -- "$p" 2>/dev/null
  done
  for f in *.md; do
    [ -e "$f" ] && git add -- "$f" 2>/dev/null
  done

  # 2) Belt-and-braces: nothing sensitive in the index?
  if git diff --cached --name-only | grep -qE '^(chats/|_inbox/)'; then
    git reset -q
    echo "[$(ts)] vault-autopush: ABORT — sensitive paths (chats/_inbox) in the index. Nothing committed."
    exit 0
  fi

  # 3) Untracked outside the allowlist: never commit, but make it visible
  strays=$(git status --porcelain 2>/dev/null | grep '^??' | cut -c4- \
           | grep -vE '^(chats/|_inbox/|graphify-out/)' | head -5 | tr '\n' ' ')
  [ -n "$strays" ] && echo "[$(ts)] vault-autopush: WARN untracked outside allowlist (NOT committed): $strays"

  # 4) Commit only if something is actually staged; check the rc
  if ! git diff --cached --quiet 2>/dev/null; then
    if git commit -q -m "$MSG"; then
      echo "[$(ts)] vault-autopush: committed ($MSG)"
    else
      echo "[$(ts)] vault-autopush: WARN commit failed — index reset, not pushing this state"
      git reset -q
    fi
  fi

  # 5) Push if origin is missing anything (including earlier unpushed commits)
  ahead=$(git rev-list --count '@{u}..HEAD' 2>/dev/null || echo 0)
  if [ "${ahead:-0}" -gt 0 ] 2>/dev/null; then
    if git push -q origin HEAD 2>/dev/null; then
      echo "[$(ts)] vault-autopush: pushed ($ahead commit(s))"
    elif git -c rebase.autoStash=true pull --rebase -q origin HEAD 2>/dev/null && git push -q origin HEAD 2>/dev/null; then
      echo "[$(ts)] vault-autopush: pushed (after rebase retry)"
    else
      echo "[$(ts)] vault-autopush: WARN push failed (offline? next trigger will retry)"
    fi
  fi
} >> "$LOG" 2>&1
exit 0
