---
description: "Undo autopilot actions — last night entirely, or targeted. Zero ceremony: under a minute from doubt to restored state."
argument-hint: "[optional: count | YYYY-MM-DD | action id aXXXXXXXX-NNN]"
---

You are undoing autopilot actions from the user's Personal OS
(journal: `~/.claude/personal-os/actions.jsonl`, or `$PERSONAL_OS_HOME/actions.jsonl` if set).

1. Without `$ARGUMENTS`: show
   `python3 ~/.personal-os/scripts/pos_actions.py list --night $(date +%F)`  # or your scripts dir
   (last night = today's date), summarize grouped (n links, n archived, …).
   Then ONE question: "Undo everything from last night?" — on yes:
   `python3 ~/.personal-os/scripts/pos_actions.py undo --night $(date +%F)`.
2. `$ARGUMENTS` = a number → `undo --last N` · a date → `undo --night <date>` · an id → `undo --id <id>`.
3. Show the output 1:1 (↩ undone / ~ skipped with reason — skipped means: the user
   already changed it themselves, so the undo leaves it alone).
4. Note at the end: every undo automatically counts as `rejected` feedback — the
   autopilot becomes more conservative in that area on its own. Nothing else to do.

Never: manually "rebuild" files instead of going through pos_actions (the journal is
the source of truth); delete anything; commit (autopush handles that, if enabled).
