---
description: "Lessons maintenance (prune loop): merge duplicates, archive cold lessons, re-validate overdue ones — nothing without a Y/N. Keeps the lesson store sharp instead of bloated."
argument-hint: "[optional: 'report' show only | 'apply' carry out the suggestions]"
---

You run **garbage collection / maintenance** over `~/vault/lessons/` — the prune part of the
Personal OS loop. Goal: the store stays sharp (good recall in the lessons hook) instead of growing
full of near-dupes, dead weight and outdated knowledge. Rules: `~/vault/CLAUDE.md`.

**Iron rule:** never delete. Archiving = **move** to `~/vault/_archive/lessons/` — IMPORTANT:
OUTSIDE `~/vault/lessons/`, because the qmd `lessons` collection (pattern `**/*.md`) would keep
indexing a subdirectory (`lessons/_archive/`) and the recall hook would keep surfacing it. Outside
the collection = out of the index, but preserved in the vault (Obsidian still sees it).
Merge/archive ONLY after an explicit Y/N from the user (no content loss without confirmation).

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

3. One concrete suggestion per finding, then ask the user Y/N (batched, don't nag one by one):
   - **Merge band (≥0.88):** FIRST read both and check it really is the same — thematically
     close ≠ duplicate (e.g. keep a security rule and a reliability rule separate). If genuine:
     the *stronger* one is the target, merge the weaker's unique content in, pull
     wikilinks/`updated:`, move the weaker to `_archive/`. Never lose content.
   - **Related band (0.82–0.88):** do NOT merge — set reciprocal `[[wikilinks]]` in both +
     pull `updated:` so the graph connects them.
   - **Stale:** quickly check the lesson still holds (maybe 1 web/tool check). Holds →
     extend `review_by` + set `updated:`. No longer holds → correct the rule
     (like a `/lesson` update) + new `review_by`.
   - **Archive candidates:** never fired + old → move to `_archive/`. First check whether it
     is a timeless principle that just rarely matches (then keep + maybe sharpen the title/rule
     so the hook finds it) instead of archiving blindly.

4. On `$ARGUMENTS` == `apply` or after a Y: carry out the changes (`mkdir -p
   ~/vault/_archive/lessons`; `mv` for archive; merge via Edit). Then run `qmd update` so the
   index drops the moved/archived lessons (otherwise they keep showing up in recall until the
   next update). No git commit (the user commits the vault themselves).

5. If the vault is clean (no/few findings): say so honestly ("store healthy, nothing to do") —
   no busywork.

6. Wrap-up: 1 line of tally (X merged, Y archived, Z re-validated) + a note that the next
   `qmd update` rebuilds the index (archived ones drop out of recall).
