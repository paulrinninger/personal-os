---
description: "Distill learnings from NEW chat imports (~/vault/chats/code/ + chats/gpt/) into the Personal OS. Incremental via state files — only processes what arrived since the last run."
argument-hint: "[optional: max number of files per source, default 10]"
---

You distill new chat sessions into the user's Personal OS (`~/vault/`, rules: `~/vault/CLAUDE.md`).
Incremental and sparing. Two sources, separate state files, same mechanics.

> **Prerequisite — import the transcripts first.**
> - `~/vault/chats/code/` is populated by `claude_to_obsidian.py`. That import is **OFF by
>   default** (it copies ALL your Claude Code transcripts into the vault — a privacy choice;
>   they stay local: the vault scaffold's `.gitignore` excludes `chats/` entirely, so raw
>   transcripts never reach a remote). Run it manually whenever you want fresh material:
>   ```bash
>   python3 ~/.personal-os/scripts/claude_to_obsidian.py        # or your scripts dir
>   ```
>   Or enable the nightly import via `import_chats_nightly` + `--schedule` at install time.
> - `~/vault/chats/gpt/` only fills when you import a ChatGPT data export via
>   `chatgpt_to_obsidian.py --zip <export.zip>` (manual, one-off per export — see docs/SETUP.md).
>
> If both folders are empty, there is simply nothing to mine yet.

Steps:

1. Determine new files (each state file lists already-processed filenames, one per line):
   ```bash
   S=~/vault/.chat_mining_state.txt; touch "$S"
   ls ~/vault/chats/code/*.md 2>/dev/null | xargs -n1 basename | grep -vxFf "$S" | head -${ARGUMENTS:-10}
   G=~/vault/.chatgpt_mining_state.txt; touch "$G"
   ls ~/vault/chats/gpt/*.md 2>/dev/null | xargs -n1 basename | grep -vxFf "$G" | head -${ARGUMENTS:-10}
   ```
   No new files in either source → report "nothing to mine", done.
2. Read each new file (skim past tool-call noise) and extract ONLY non-trivial gold:
   - **lesson**: an error with a non-obvious cause + fix, transferable to other projects
   - **idea**: hooks the user voiced (verbatim!), video/posting/product ideas
   - **knowledge**: strategy substance (audience psychology, pricing, positioning)
   - **profile**: stable new facts about the user's goals/standards/style
   Be selective: many files yield NOTHING — that's fine.
   **PII rule for gpt chats:** ChatGPT history is often more personal than coding
   transcripts (health, finances, relationships). Never distill sensitive personal detail
   into regular vault notes — if in doubt, leave it in the raw chat (which stays local).
3. Write with mandatory dedup: `grep -ril "<keywords>"` in the target folder — hit → EXTEND the
   existing note (updated:, evidence bullet, add source) instead of a new file. New notes per the
   templates in `~/vault/_templates/`, `source:` = the chat path, ≥2 wikilinks.
4. Append the processed filenames (including the ones with no findings!) to the matching state file:
   ```bash
   echo "<filename>" >> ~/vault/.chat_mining_state.txt      # for chats/code/
   echo "<filename>" >> ~/vault/.chatgpt_mining_state.txt   # for chats/gpt/
   ```
5. No git. Report: n files processed, m notes new/extended (paths), rest skipped.
