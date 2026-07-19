---
description: "Show the night journal: what the autopilot executed overnight + yesterday's residue. No review ritual anymore — rollback via /undo."
argument-hint: "[optional: a YYYY-MM-DD date]"
---

You are showing the user's nightly Personal OS journal. Since the autopilot rework,
dream notes are JOURNALS (`status: journal`), not proposal todo lists: the low-risk
layer (links, archive, status fields, queue drains) was already EXECUTED by
`pos_autopilot.py` and is reversible via `/undo`.

1. Find the newest note (`ls -t ~/vault/_inbox/dreams/*-dream.md | head -1`, or the one
   matching the date in `$ARGUMENTS`) and show it compactly: "Executed tonight" in
   full, yesterday's residue in full, the rest as one line per section.
2. Add one line of context:
   ```bash
   python3 ~/.personal-os/scripts/pos_actions.py list --night <date>   # or your scripts dir
   ```
   — the action count; if anything looks off, point at `/undo`.
3. No note found → show the last run (`tail ~/.local/state/personal-os/logs/dream.log`,
   or `$PERSONAL_OS_LOG_DIR/dream.log` if set) and whether `dream.off`/`autopilot.off`
   exists in the engine home (`~/.claude/personal-os/` by default). Done — change nothing.
4. Tier-2 hints in the note (merge candidates, "sharpen the rule", venture patterns)
   are hints only: act on request only (→ /lessons-gc, edit the lesson, or
   `/lesson --guard`). Producer drafts keep their own flow: `/producer review`.

Kill switches: `touch ~/.claude/personal-os/autopilot.off` (execution off, passes keep
running) · `touch ~/.claude/personal-os/dream.off` (everything off).
Never: delete dream notes, commit anything.
