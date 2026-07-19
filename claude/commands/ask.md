---
description: "One question, all memories: search qmd (vault, semantic) + chat history + graph in parallel and answer with sources. Never ask which backend first."
argument-hint: "<question — e.g. 'where was the decision about X?' or 'which email does the deploy need?'>"
---

You answer the user's question from THEIR entire memory. NEVER ask which backend —
probe all surfaces in parallel (one block, several Bash calls, each ≤10s; silently
drop any empty/failed surface):

```bash
qmd vsearch "$ARGUMENTS" -n 8 --format json          # vault, semantic (lessons/knowledge/logs)
grep -rli "<core term>" ~/vault/chats/ 2>/dev/null | head -10   # chat history (then targeted grep -n -C2 in the top hits)
[ -f ~/vault/graphify-out/graph.json ] && graphify query "$ARGUMENTS" --graph ~/vault/graphify-out/graph.json
```

Synthesis rules:
1. Prose, 5–15 lines, **every claim with a source** (`~/vault/…`, `#docid` for qmd hits).
2. If surfaces contradict each other: say so — and prefer the newer dated source.
3. Nothing found: ONE honest line + which queries were tried. NEVER invent.
4. Depth: only if the top hit clearly contains the answer, ONE `qmd get <#docid>`
   or Read on it; never open more than 3 files.
