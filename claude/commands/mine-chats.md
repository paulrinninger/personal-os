---
description: "Distill learnings from NEW chat imports (~/vault/chats/code/) into the Personal OS. Incremental via a state file — only processes what arrived since the last run."
argument-hint: "[optional: max number of files, default 30]"
---

You distill new chat sessions into the user's Personal OS (`~/vault/`, rules: `~/vault/CLAUDE.md`).
Incremental and sparing.

> **Prerequisite — import the transcripts first.** `/mine-chats` reads from `~/vault/chats/code/`,
> which is populated by `claude_to_obsidian.py`. That import is **OFF by default** (it copies ALL your
> Claude Code transcripts into the vault — a privacy choice; they stay local: the vault scaffold's `.gitignore` now excludes `chats/` entirely, so raw transcripts never reach a remote).
> Run it manually whenever you want fresh material:
> ```bash
> python3 ~/.personal-os/scripts/claude_to_obsidian.py        # or your scripts dir
> ```
> Or enable the nightly import via `import_chats_nightly` + `--schedule` at install time. If
> `~/vault/chats/code/` is empty, there is simply nothing to mine yet.

Steps:

1. Determine new files (the state file lists already-processed filenames, one per line):
   ```bash
   S=~/vault/.chat_mining_state.txt; touch "$S"
   ls ~/vault/chats/code/*.md 2>/dev/null | xargs -n1 basename | grep -vxFf "$S" | head -${ARGUMENTS:-30}
   ```
   No new files → report "nothing to mine", done.
2. Read each new file (skim past tool-call noise) and extract ONLY non-trivial gold:
   - **lesson**: an error with a non-obvious cause + fix, transferable to other projects
   - **idea**: hooks the user voiced (verbatim!), video/posting/product ideas
   - **knowledge**: strategy substance (audience psychology, pricing, positioning)
   - **profile**: stable new facts about the user's goals/standards/style
   Be selective: many files yield NOTHING — that's fine.
3. Write with mandatory dedup: `grep -ril "<keywords>"` in the target folder — hit → EXTEND the
   existing note (updated:, evidence bullet, add source) instead of a new file. New notes per the
   templates in `~/vault/_templates/`, `source:` = the chat path, ≥2 wikilinks.
4. Append the processed filenames (including the ones with no findings!) to the state file:
   ```bash
   echo "<filename>" >> ~/vault/.chat_mining_state.txt
   ```
5. No git. Report: n files processed, m notes new/extended (paths), rest skipped.
