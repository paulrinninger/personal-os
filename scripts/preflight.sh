#!/bin/sh
# preflight.sh — makes "did the typecheck actually run?" deterministically checkable.
# Runs the FULL tsc (NOT tsconfig.app.json — that one misses node/edge code) plus an
# author check, then stamps .git/pos-preflight-ok with the HEAD SHA. guard.py (rule
# deploy-no-preflight) demands a fresh marker (same SHA, <30 min) before push/deploy.
#
# Expected author email (optional, checked in this order):
#   1. $PERSONAL_OS_GIT_AUTHOR_EMAIL
#   2. the first "author_email" found in <PERSONAL_OS_HOME>/guards.json rules
# Neither set -> the author check is skipped (typecheck still runs).
#
# Usage: preflight.sh [project-dir]
set -e
cd "${1:-.}"
GITDIR=$(git rev-parse --git-dir)

PO="${PERSONAL_OS_HOME:-$HOME/.claude/personal-os}"
EXPECTED="${PERSONAL_OS_GIT_AUTHOR_EMAIL:-}"
if [ -z "$EXPECTED" ] && [ -f "$PO/guards.json" ]; then
  EXPECTED=$(python3 - "$PO/guards.json" 2>/dev/null <<'PY' || true
import json, sys
try:
    cfg = json.load(open(sys.argv[1]))
    for r in cfg.get("rules", []):
        if r.get("author_email"):
            print(r["author_email"])
            break
except Exception:
    pass
PY
)
fi

if [ -n "$EXPECTED" ]; then
  echo "-> author check"
  EMAIL=$(git config user.email || true)
  if [ "$EMAIL" != "$EXPECTED" ]; then
    echo "x  user.email='$EMAIL' (expected $EXPECTED) — some deploy pipelines silently"
    echo "   ignore commits from an unknown author (no deploy, no error)."
    echo "   Fix: git config user.email $EXPECTED   (repo-local, never --global)"
    exit 1
  fi
else
  echo "-> author check skipped (no author_email in guards.json or PERSONAL_OS_GIT_AUTHOR_EMAIL)"
fi

if [ -f tsconfig.json ]; then
  echo "-> full typecheck (tsc --noEmit, main tsconfig)"
  if [ -f package.json ] && grep -q '"typecheck"' package.json; then
    npm run -s typecheck
  else
    npx tsc --noEmit
  fi
else
  echo "-> no tsconfig.json — typecheck skipped"
fi

git rev-parse HEAD > "$GITDIR/pos-preflight-ok"
echo "ok preflight — marker stamped ($(git rev-parse --short HEAD), 30 min TTL)"
