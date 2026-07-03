#!/bin/sh
# vault_autopush.sh — commit + push any pending vault changes to its remote.
#
# Intended as a Stop hook (runs at the end of every Claude Code session) so your vault
# is backed up within seconds of a change, not just at the next nightly run. Fails
# open: never blocks or errors out a session. Deliberately `git add -A` here — unlike
# a scoped session-log commit, this is a generic "sync everything pending" job.
#
# Requires the vault to already be a git repo with a remote configured
# (`git -C <vault> remote add origin <url>`) — if not, this is a silent no-op.
#
# Config: PERSONAL_OS_VAULT (default ~/vault), PERSONAL_OS_LOG_DIR (debug log).
set -u

VAULT="${PERSONAL_OS_VAULT:-$HOME/vault}"
VAULT=$(eval echo "$VAULT")
LOG_DIR="${PERSONAL_OS_LOG_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/personal-os/logs}"
mkdir -p "$LOG_DIR" 2>/dev/null
LOG="$LOG_DIR/hooks.log"

ts() { date '+%F %T'; }

[ -d "$VAULT/.git" ] || exit 0

{
  cd "$VAULT" || exit 0
  if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
    git add -A
    git commit -q -m "auto-sync $(date '+%F %T')"
    if git push -q 2>/dev/null; then
      echo "[$(ts)] vault-autopush: committed + pushed"
    else
      # Race with a parallel session or the nightly job: rebase with autostash, retry once.
      if git -c rebase.autoStash=true pull --rebase -q 2>/dev/null && git push -q 2>/dev/null; then
        echo "[$(ts)] vault-autopush: committed + pushed (after rebase retry)"
      else
        echo "[$(ts)] vault-autopush: WARN push failed (offline? no remote? next trigger will retry)"
      fi
    fi
  fi
} >> "$LOG" 2>&1
exit 0
