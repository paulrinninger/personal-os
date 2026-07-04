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

**Risk tiering (introduced 2026-07-04, after user feedback "why do I have to confirm
everything"):** not every checkbox deserves the same yes/no bar. Only ask when an action
changes/removes real content or creates something new the user hasn't seen. Purely additive,
meaning-preserving, trivially-reversible actions (reciprocal wikilinks) run automatically —
the user still sees them, just bundled in the final report (step 6), not as an individual
question. Automatic still means logged (step 3), not untracked.

1. Read the newest dream note's open `- [ ]` checkboxes.
2. **Treat each checkbox type differently:**
   - **Connection suggestion (`^d…-b…`) — AUTOMATIC, no question:** add a reciprocal
     `[[wikilink]]` under `## Links` in BOTH notes (don't touch anything else). Changes no
     meaning, trivially reversible by removing the link.
   - **Merge / cross-link candidate (`^d…-m…`):** don't merge yourself — run `/lessons-gc`,
     which already has its own risk tiering built in (cross-link automatic, merge needs a yes).
   - **Hot lesson (`^d…-f…`) — needs a yes, but ONE round:** open and read the lesson
     immediately; if a real sharpening is possible, present the CONCRETE proposal (exact text,
     exact location) for confirmation directly — don't ask "should I sharpen this?" first and
     show the actual proposal in a second round, that doubles the back-and-forth for no reason.
     If honest reading turns up nothing substantial ("already sharp enough"), say so directly
     rather than forcing a cosmetic edit.
   - **Inbox-triage entry (`^d…-t…`) — needs a yes, but ONE round, with a CORRECTED target:**
     read the card itself (not just title/score) and check the suggested embedding target
     against the actual content — embedding matches are wrong more often for generic PDF
     reference content than for lessons (verified 2026-07-04: 4 of 10 pointed at the wrong
     project). If the target doesn't fit, propose the CORRECTED destination in the same
     question (domain folders under `knowledge/{business,marketing,design,coding,content}/`,
     or `profile/<name>.md` for bio/skills material about the user themselves — there is no
     `knowledge/reference` folder, that phrasing is stale). For multiple copies of the same
     source document (spot near-identical `## Summary` text), promote once and park the rest —
     don't create the same note multiple times.
   - **Venture pattern (`^d…-v…`) — needs a yes:** no file to change — it's a pure observation.
     Yes = "this pattern was accurate/useful", no = "false alarm, not actually similar." Just
     log the feedback (step 3) — there's nothing to execute.
3. Append one line per decision (automatic OR yes/no) to `~/.claude/personal-os/dream-feedback.jsonl`
   (path via `PERSONAL_OS_HOME` if set): `{"id":"<block-id>","pass":"connections|gc|fires|triage|ventures","verdict":"accepted|rejected","ts":"<ISO>"}`.
   This is what makes the next run's thresholds adapt — no ML, just counters. (Without `"ventures"`
   here, feedback on venture patterns would never reach `adaptive_params("ventures")`, which reads
   exactly this file.)
4. Check off reviewed boxes in the dream note (`- [x]`); once all are handled, set `status: reviewed`
   in its frontmatter.
5. **Count-check before reporting (mandatory, not optional):** the number of originally-open
   `- [ ]` boxes MUST equal the number now checked `- [x]` (compare `grep -c` before/after). A
   mismatch means an item was silently skipped — go back and handle it, don't just report a
   smaller number. (2026-07-04: this exact thing happened once — a triage card got skipped
   mid-review because its filename was easy to confuse with two similar ones; only the count-
   check after the fact caught it, not the review pass itself.)
6. Report: N accepted / M rejected (report automatic + yes/no together, counted separately),
   which files changed.

Never: delete dream notes yourself (let the user clean up old ones), change a live note's
CONTENT without a yes (adding a reciprocal wikilink is not a content change), commit anything.
