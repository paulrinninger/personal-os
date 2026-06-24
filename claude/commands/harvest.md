---
description: Process the auto-harvest queue — distill lessons & ideas from sessions that ended without /save into a review inbox. $0, local, you stay in the loop.
argument-hint: "[optional: 'review' = only sift/promote inbox drafts]"
---

You close the self-improvement loop for sessions that ended **without `/save`** — the enqueue ran
automatically (Stop hook); the distillation happens here in THIS interactive session ($0, no external/
headless LLM pipeline → consistent with the vault's $0 policy). Rules: `~/vault/CLAUDE.md`.

**`review` mode** (`$ARGUMENTS` == `review`): skip the queue, only sift `~/vault/_inbox/**` — per draft
Y/N: promote (to `lessons/` or `ideas/`, dedup) or park (`status: parked`, never delete). Then stop.

Otherwise — process the queue:

1. Read the queue: `~/.claude/personal-os/harvest-queue.jsonl` (lines: `{session_id, transcript_path, cwd, ts}`).
   Empty → say "nothing to harvest" and stop.
2. For each entry read its `transcript_path` (missing/unreadable → drop the entry). **Skip** if the session
   already wrote a vault log — PRECISE (a real write, not a path mention):
   `grep -qE '"file_path":"[^"]*vault/([^"]*/)?logs/[^"]*\.md"' <transcript>` → already harvested via `/save`.
3. Harvest like `/save` step 4, but into the **review inbox** instead of the recall index:
   - **Lesson candidate** (error with a non-obvious cause, transferable): duplicate check
     `grep -ril "<keywords>" ~/vault/lessons/`. Hit → propose updating the existing note. No hit → draft
     `~/vault/_inbox/lessons/<slug>.md` (template `~/vault/_templates/lesson.md`, plus `status: draft`).
     Max 3/session. Do NOT capture trivialities, typos, one-off flakes.
   - **Idea** (one the USER voiced): draft `~/vault/_inbox/ideas/<kind>/<slug>.md`. Max 3/session.
4. Show the drafts compactly (title + rule sentence). Since you're in the loop: bundled Y/N per draft.
   **Y** → move the draft into `~/vault/lessons/` or `~/vault/ideas/<kind>/` (real note, drop/normalize
   `status`), dedup. **N/later** → it stays in `_inbox` (surfaces in `/os doctor`).
5. Remove processed entries from the queue (rewrite the file without them). No git. `_inbox/` is
   deliberately **outside** the qmd collection → drafts don't pollute recall until promoted.
6. Report: X sessions processed, Y lessons + Z ideas drafted, of those promoted/open, queue now empty.
