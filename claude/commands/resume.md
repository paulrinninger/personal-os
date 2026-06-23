---
description: Resume context from the vault — read the newest session logs + architecture decisions and summarize state.
argument-hint: "[optional: a topic to focus the recap on]"
---

You are resuming context for the current project from the user's vault (local $0 memory; see
`~/vault/CLAUDE.md`). Also remember a graphify code graph may exist at `graphify-out/graph.json` —
prefer `graphify query "<question>"` over reading many files when answering codebase questions.

Steps:

1. Resolve project + locate notes:
   ```bash
   P=$(basename "$PWD")
   DIR=~/vault/$P; [ -d "$DIR" ] || DIR=~/vault
   echo "project=$P dir=$DIR"
   ls -t "$DIR"/logs/*.md 2>/dev/null | head -3
   ls "$DIR"/architecture/decisions.md 2>/dev/null
   ```
2. Read the **3 most recent** log files in `<dir>/logs/` and `architecture/decisions.md` if it exists.
   If `$ARGUMENTS` is given, also grep the vault for that topic and read the top matches.
3. If `graphify-out/graph.json` exists, note it's available (don't dump it).
4. Produce a tight recap for the user:
   - **Stand / Current state:** where things are.
   - **Zuletzt / Recently done:** from the newest logs.
   - **Offen / Open items:** pending next steps.
   - **Relevante Notizen / Relevant notes:** the vault notes you read (as paths).
   Keep it scannable. Do not modify any files.
