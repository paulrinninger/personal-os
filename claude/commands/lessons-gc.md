---
description: "Lessons maintenance (prune loop): merge duplicates, archive cold lessons, re-validate overdue ones — content never changes without a Y/N, pure cross-link wikilinks run automatically. Keeps the lesson store sharp instead of bloated."
argument-hint: "[optional: 'report' show only | 'apply' carry out the suggestions]"
---

You run **garbage collection / maintenance** over `~/vault/lessons/` — the prune part of the
Personal OS loop. Goal: the store stays sharp (good recall in the lessons hook) instead of growing
full of near-dupes, dead weight and outdated knowledge. Rules: `~/vault/CLAUDE.md`.

**Iron rule:** never delete. Archiving = **move** to `~/vault/_archive/lessons/` — IMPORTANT:
OUTSIDE `~/vault/lessons/`, because the qmd `lessons` collection (pattern `**/*.md`) would keep
indexing a subdirectory (`lessons/_archive/`) and the recall hook would keep surfacing it. Outside
the collection = out of the index, but preserved in the vault (Obsidian still sees it).
**Risk tiering (2026-07-04):** merging/archiving/rule corrections change real content or the
store's makeup → ONLY after an explicit Y/N. Pure related/cross-link wikilinks change no meaning
and are trivially reversible → run automatically, but still get reported together in the wrap-up
(step 6), not silently.

Steps:

1. Generate the report (local & $0; embeds lesson identities via `nomic-embed-text`):
   ```bash
   python3 ~/.claude/personal-os/os_lessons.py gc
   ```
   Returns: **archive candidates** (never fired + >90 days), **stale** (review_by overdue),
   **merge candidates** (cosine ≥ 0.88 = true duplicate) and **related/cross-link**
   (0.82–0.88 = thematically close, do NOT merge — only link). Requires ollama for the
   similarity bands; if ollama is absent it still reports cold/stale.

2. Summarize the report scannably. If `$ARGUMENTS` == `report`: stop here.

3. Treat each finding by its risk tier:
   - **Related band (0.82–0.88) — AUTOMATIC, no question:** set reciprocal `[[wikilinks]]` in
     both + pull `updated:` so the graph connects them. Do NOT merge.
   - **Merge band (≥0.88) — needs a Y/N, but ONE round:** FIRST read both and check it really is
     the same — thematically close ≠ duplicate (e.g. keep a security rule and a reliability rule
     separate). If genuine: present the CONCRETE merge plan directly (which lesson is
     stronger/the target, what unique content from the weaker one gets folded in) — don't ask
     "should I merge?" first and show the plan in a second round. After a yes: the *stronger*
     one is the target, merge the weaker's unique content in, pull wikilinks/`updated:`, move
     the weaker to `_archive/`. Never lose content.
   - **Stale — tiered:** quickly check the lesson still holds (maybe 1 web/tool check). Holds →
     **automatically** extend `review_by` + set `updated:` (pure deadline extension, no content
     changes). No longer holds → **needs a Y/N**, present the concrete correction directly
     (like a `/lesson` update) + new `review_by`.
   - **Archive candidates — needs a Y/N:** never fired + old → move to `_archive/`. Removes it
     from active recall, a content decision even though reversible. First check whether it is a
     timeless principle that just rarely matches (then keep + maybe sharpen the title/rule so
     the hook finds it, as part of the same proposal) instead of archiving blindly.

4. On `$ARGUMENTS` == `apply` or after a Y: carry out the changes (`mkdir -p
   ~/vault/_archive/lessons`; `mv` for archive; merge via Edit). Then run `qmd update` so the
   index drops the moved/archived lessons (otherwise they keep showing up in recall until the
   next update). No git commit (the user commits the vault themselves).

5. If the vault is clean (no/few findings): say so honestly ("store healthy, nothing to do") —
   no busywork.

6. **Count-check before the wrap-up (mandatory):** the number of findings from step 1 (archive
   candidates + stale + merge + related, combined) MUST equal the number actually handled
   (auto-executed + confirmed yes + rejected no + explicitly deferred "later"). A mismatch means
   one was skipped while working through the list — go back and handle it, don't wrap up with a
   smaller number.

7. Wrap-up: 1 line of tally (X auto-linked, Y merged, Z archived, W re-validated) + a note that
   the next `qmd update` rebuilds the index (archived ones drop out of recall).
