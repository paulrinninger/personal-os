# Vault — Instructions for Claude Code · Anweisungen für Claude Code

This is your central **Obsidian knowledge vault** — persistent, declarative memory across
sessions and projects (decisions, architecture, session logs, imported chats). It complements,
but does not replace, the per-project graphify code graph (`graphify-out/graph.json`) and
Claude's `~/.claude` auto-memory.

> **Arbeitsteilung / division of labour**
> - **graphify graph** = *how the code is structured* (machine-generated, per repo).
> - **This vault** = *what was decided & done* (human/Claude-authored notes + session logs).
> - **`~/.claude` auto-memory** = Claude's cross-session facts index.

## Struktur / Structure

```
~/vault/
├── HOME.md                 # Personal-OS entry point + /os dashboard (auto-block)
├── _templates/             # note templates: lesson, idea, project-hub, decision, profile, knowledge
├── profile/                # who you are: goals, standards, style — Claude reads these and acts on them
├── knowledge/              # distilled domain knowledge
│   └── {coding,design,marketing,business}/
├── lessons/                # FLAT — cross-project error+fix+why (domain via frontmatter)
├── ideas/{hooks,video,posting,product}/      # idea pool
├── projects/               # 1 hub note per project: <kebab-name>.md (status, stack, paths)
├── permanent/              # atomic Zettelkasten notes (1 concept each, no clear domain)
├── _inbox/                 # harvest drafts (status: draft) — outside the qmd collection, not in recall
├── logs/                   # cross-project session logs
├── chats/{code,web}/       # imported Claude conversations (auto, rule-based)
├── graphify-out/           # vault knowledge graph (machine-generated, exclude in Obsidian)
└── <project>/              # optional per-project subtree
    ├── architecture/       # decisions.md, system notes
    ├── pipeline/  data/  features/
    └── logs/               # this project's session logs (/save writes here)
```

## Zettelkasten-Regeln / rules

- Use `[[wikilinks]]`, **not** markdown links, for internal references — link liberally (≥2 per note).
- Every note has YAML frontmatter; filenames in `kebab-case`; one concept per permanent note.
- Write user-facing content **bilingual DE + EN** where it matters (a standing convention — adapt to your own languages).

### Standard frontmatter
```yaml
---
title: Note Name
tags: [project, topic]
created: YYYY-MM-DD
updated: YYYY-MM-DD
status: active
type: permanent        # or: log, decision, chat, lesson, idea, hub, profile, knowledge
---
```

Optional fields (Personal OS — use where they apply):
- `domain: coding|marketing|design|business|content|ops` — recommended for lesson/idea/knowledge/hub
- `project: <kebab-name>|cross` — project link
- `confidence: high|medium|low` — lesson/knowledge only: how well established?
- `kind: hook|video|posting|product` — type: idea only
- `source: <path-or-origin>` — migrated/distilled notes (source path = idempotency marker)
- `review_by: YYYY-MM-DD` — time-sensitive lessons; /lessons-gc flags overdue ones
- `status:` for ideas: `active` = open, `done` = shipped, `parked` = later

Templates for every type: `~/vault/_templates/`.

### Never do
- Don't delete notes without asking. · Keine Notiz ohne Rückfrage löschen.
- Don't use markdown links for internal notes (use wikilinks).
- Don't create notes without frontmatter.
- In lessons, NEVER record an unverified workaround as a "Fix". "## Fix" = provably works
  (with evidence); failed attempts go under "## Was NICHT funktioniert (verifiziert)" — both
  lists are equally valuable (dead ends cost every future session otherwise).
- Don't name projects/folders under your home dir like the OS folders (knowledge, lessons,
  ideas, projects, profile, _templates) — collides with /save routing.

## Graph-Query-Routing (alles $0 / all $0)

- Code questions → in the repo: `graphify query "<question>"`.
- Lessons/decisions/knowledge → `graphify query "<question>" --graph ~/vault/graphify-out/graph.json`
- Cross-project → `graphify query "<question>" --graph ~/.graphify/global-graph.json`
- Limits: lexical/keyword-based — hits depend on title/heading words. Vault-graph traversal works
  only thanks to wikilink injection (`scripts/vault_inject_wikilinks.py`, run after every
  `graphify update ~/vault`).
- **Meaning search (qmd, $0 local)** → `qmd query "<question>"` (hybrid: BM25+vector+RRF+reranker,
  multilingual embeddings). Finds notes by **meaning**, not title words — closes exactly graphify's
  lexical gap; returns cited passages + score, then `qmd get <docid>` for the full text. Pure modes
  without an LLM: `qmd search` (BM25), `qmd vsearch` (vector). Config: `~/.config/qmd/index.yml`;
  index: `~/.cache/qmd/` (outside the vault).
- **Routing rule of thumb:** "where is… / do we know… / have we got something on this?" (meaning)
  → **qmd**; "what's connected to X / structure / cross-project paths?" → **graphify**. Both $0 &
  local, complementary (qmd = meaning/passages, graphify = structure/links/communities).

## Kosten / cost

This vault and its chat-import pipeline are **100 % local & $0** — tagging/wikilinks are rule-based
(regex + keyword map), no LLM/API calls. Keep it that way unless a local-ollama pass is explicitly added.
