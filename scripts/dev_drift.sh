#!/bin/sh
# dev_drift.sh — MAINTAINER tool, read-only. Compares the repo's shippable assets
# (claude/commands/*.md + claude/hooks/*.py) against the live equivalents under
# ~/.claude/ and prints a per-file drift summary. Useful when the live system is
# hardened first and the repo has to be brought to parity (or vice versa).
#
# This is NOT the user-facing drift check — that is `install.py --check-drift`,
# which compares against the install manifest. This one is for developing in a
# checkout next to a live install.
#
# Usage: scripts/dev_drift.sh [live-claude-dir]   (default ~/.claude)
set -u

REPO=$(CDPATH= cd "$(dirname "$0")/.." && pwd)
LIVE="${1:-$HOME/.claude}"

same=0; differ=0; missing=0

compare() {  # compare <repo-file> <live-file> <label>
  if [ ! -e "$2" ]; then
    echo "  MISSING  $3   (no live counterpart)"
    missing=$((missing + 1))
  elif diff -q "$1" "$2" >/dev/null 2>&1; then
    same=$((same + 1))
  else
    n=$(diff "$1" "$2" 2>/dev/null | grep -c '^[<>]')
    echo "  DIFFERS  $3   (~$n changed lines)"
    differ=$((differ + 1))
  fi
}

echo "dev drift: repo $REPO  vs  live $LIVE"
echo
echo "commands:"
for f in "$REPO"/claude/commands/*.md; do
  [ -e "$f" ] || continue
  compare "$f" "$LIVE/commands/$(basename "$f")" "commands/$(basename "$f")"
done
echo "hooks:"
for f in "$REPO"/claude/hooks/*.py; do
  [ -e "$f" ] || continue
  compare "$f" "$LIVE/hooks/$(basename "$f")" "hooks/$(basename "$f")"
done
echo
echo "summary: $same identical · $differ differ · $missing missing live"
echo "(read-only — nothing was changed. Diff a single file: diff <repo> <live>)"
exit 0
