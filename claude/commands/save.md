---
description: Write a dated session log to the vault (~/vault/<project>/logs/) with wikilinks. Does not commit git.
argument-hint: "[optional short topic slug, e.g. chat-memory]"
---

You are saving a **session log** into the user's vault so the next session can resume context.
This is part of the local, $0 Personal OS memory setup (see `~/vault/CLAUDE.md`).

Steps:

1. Run this to resolve date + project + target dir:
   ```bash
   D=$(date +%Y-%m-%d); P=$(basename "$PWD")
   DIR=~/vault/$P/logs; [ -d ~/vault/$P ] || DIR=~/vault/logs
   mkdir -p "$DIR"; echo "date=$D project=$P dir=$DIR"
   ```
2. Pick a slug: use `$ARGUMENTS` if given, else derive a short kebab-case slug from the session's main theme.
3. Write `"$DIR/$D-<slug>.md"` (if it already exists, append a `## <HH:MM> update` section instead of overwriting). Use this frontmatter + structure:
   ```markdown
   ---
   title: <one-line title>
   tags: [<project>, <topic>]
   created: <D>
   updated: <D>
   status: active
   type: log
   ---

   ## Was gemacht / What was done
   - <bullets — concrete changes, files touched as `path:line`>

   ## Entscheidungen / Decisions
   - <key decisions + the why>

   ## Offen / Pending
   - <next steps, open questions>

   ## Links
   - [[<related-note>]]  (link liberally to vault notes; a non-existent target is fine)
   ```
4. **Harvest — lessons & ideas (automatic, max 3+3):** scan the session:
   a) Was there an error with a non-obvious cause that got fixed and could recur in OTHER
      projects? → check for a duplicate:
      `grep -ril "<2-3 keywords>" ~/vault/lessons/ 2>/dev/null`. Hit → update the existing
      note (`updated:`, append an evidence bullet). No hit → new note at
      `~/vault/lessons/<kebab-slug>.md` via the template `~/vault/_templates/lesson.md`.
      Do NOT capture: project-specific trivialities, typos, one-off flakes.
   b) Did the user voice an idea (hook, video, posting, product, a feature elsewhere)? →
      `~/vault/ideas/<kind>/<kebab-slug>.md` via `~/vault/_templates/idea.md`. Only ideas the
      USER voiced or explicitly liked — do not dump your own unsolicited brainstorms.
5. Link every newly created note in the `## Links` block of the session log and update the
   project hub `~/vault/projects/<project>.md` (if it exists): the `Stand:`/`updated:` fields
   and possibly `## Offen` (max 5 bullets).
6. Keep it concise and factual. Write bullets bilingually (DE + EN) only where nuance matters; otherwise short is fine.
7. **Do NOT run git commit/push** — the user keeps their own commit-push-deploy routine. Just write the file.
8. Report: the written log path + a 1-line summary + "Captured: <n> lessons, <m> ideas" with
   paths — the user can veto by voice (set those notes to `status: parked`, NEVER delete
   without asking).
