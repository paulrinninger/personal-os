---
description: Show or review the nightly "dream" note — a suggestions-only digest produced by the optional overnight consolidation pass. 'review' walks its checkboxes and executes accepted ones via the existing commands.
argument-hint: "[optional: 'review' | a YYYY-MM-DD date]"
---

You're working with the optional nightly "dreaming" pass (`dream_run.sh` / `dream.py`, registered
via the installer's `--schedule-dream` flag). It writes ONE proposal note per night to
`~/vault/_inbox/dreams/YYYY-MM-DD-dream.md` — condensed residue from yesterday, candidate
`[[wikilinks]]` between notes that don't reference each other, lesson merge/cross-link candidates,
firing-pattern observations, and a ranked slice of the review inbox. Nothing in it has been applied;
it is pure suggestion. Kill switch: a file named `dream.off` in the engine's home dir
(`~/.claude/personal-os/dream.off` by default) — dreaming skips itself while that file exists.

**Display mode** (default, or `$ARGUMENTS` is a date):

1. Find the note (`ls -t ~/vault/_inbox/dreams/*-dream.md | head -1`, or the one matching the given
   date) and show it compactly: each section with its open `- [ ]` count, the residue section in full.
2. No note found → say when the dream script last ran (`tail ~/.local/state/personal-os/logs/dream.log`,
   or `$PERSONAL_OS_LOG_DIR/dream.log` if set) and whether `dream.off` exists. Stop — change nothing.

**`review` mode** (`$ARGUMENTS` == `review`):

1. Read the newest dream note's open `- [ ]` checkboxes. Walk them with the user (bundle a few per
   question), one line each.
2. **On yes, execute through the EXISTING commands/flows — never invent your own:**
   - Connection suggestion (`^d…-b…`): add a reciprocal `[[wikilink]]` under `## Links` in BOTH notes.
     Don't touch anything else in either note.
   - Merge / cross-link candidate (`^d…-m…`): don't merge yourself — run `/lessons-gc` (it asks Y/N there).
   - Hot lesson (`^d…-f…`): open the lesson, propose sharpening the rule, only edit after a yes.
   - Inbox-triage entry (`^d…-t…`): treat exactly like `/harvest review` — promote (dedup first) or
     mark `status: parked`.
   - Venture pattern (`^d…-v…`): no file to change — it's a pure observation. Yes = "this pattern
     was accurate/useful" (the new project really does resemble past failures), no = "false alarm,
     not actually similar." Either way just log the feedback (step 3) — there's nothing to execute.
3. Append one line per decision to `~/.claude/personal-os/dream-feedback.jsonl` (path via
   `PERSONAL_OS_HOME` if set): `{"id":"<block-id>","pass":"connections|gc|fires|triage|ventures","verdict":"accepted|rejected","ts":"<ISO>"}`.
   This is what makes the next run's thresholds adapt — no ML, just counters. (Without `"ventures"`
   here, feedback on venture patterns would never reach `adaptive_params("ventures")`, which reads
   exactly this file.)
4. Check off reviewed boxes in the dream note (`- [x]`); once all are handled, set `status: reviewed`
   in its frontmatter.
5. Report: N accepted / M rejected, which files changed.

Never: delete dream notes yourself (let the user clean up old ones), edit a live note without a yes,
commit anything.
