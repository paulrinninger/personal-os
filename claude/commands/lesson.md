---
description: Capture a cross-project lesson (error + fix + why) into ~/vault/lessons/. Dedupes before writing.
argument-hint: "[optional: short description, e.g. 'vercel env vars need a redeploy']"
---

You are writing a **lesson** into the user's Personal OS (`~/vault/lessons/`, rules: `~/vault/CLAUDE.md`).
A lesson = error + fix + why, phrased as a transferable rule.

Steps:

1. Determine the content: from `$ARGUMENTS`, else from the most recent error+fix in this session.
   If both are missing: ONE short clarifying question, no more.
2. Duplicate check (mandatory):
   ```bash
   grep -ril "<2-3 keywords>" ~/vault/lessons/ 2>/dev/null
   ```
   Hit → read and UPDATE that note (set `updated:`, append an evidence bullet under
   `## Fehler`, raise `confidence:` if warranted). No new file.
3. Otherwise a new note `~/vault/lessons/<kebab-slug>.md` exactly per the template
   `~/vault/_templates/lesson.md`. Frontmatter: derive `domain:` from context
   (coding|marketing|design|business|content|ops), `project:` = `basename "$PWD"` or `cross`,
   estimate `confidence:` honestly (happened once = medium).
3b. If `$ARGUMENTS` contains `--guard` (or the rule is deterministically checkable and
   keeps recurring): additionally draft a guard entry for
   `~/.claude/personal-os/guards.json` — matcher (regex on the command), probe (an
   existing probe from `~/.claude/hooks/guard.py`, or name a new one), decision
   (ask|deny|warn), reason (1 line, distilled from the rule), lesson wikilink — and
   show it for Y/N before appending. A new probe needed → mark the entry as a TODO
   (`enabled: false`), never guess.
   **Time-sensitive?** If the lesson depends on external behaviour that can change
   (tool/API/platform behaviour, prices, UI), also set `review_by: <YYYY-MM-DD>`
   (default +6 months). `/lessons-gc` reports overdue ones for re-validation instead of
   treating them as true forever. Timeless principles need no `review_by`.
4. Set ≥2 wikilinks (the project hub `[[<project>]]` counts). Title = an imperative rule.
   Keep it short and scannable — body under 25 lines.
5. No git commit. Report: the path + the rule in one sentence.
