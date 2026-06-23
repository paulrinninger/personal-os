# Commands & Hooks Reference / Befehls- & Hook-Referenz

> **DE zuerst, dann EN.** Each section has a German half and an English half.

Vollständige Referenz: die 7 Slash-Commands, die 2 Hooks und die Engine `os_lessons.py` —
was jedes tut, wann es läuft, was es liest/schreibt.

Complete reference: the 7 slash commands, the 2 hooks, and the `os_lessons.py` engine —
what each does, when it runs, what it reads/writes.

---

## 1. Slash-Commands / Slash commands

Installiert nach / installed to: `~/.claude/commands/`

### DE

| Befehl | Was es tut | Wann | Liest / Schreibt |
|--------|-----------|------|------------------|
| `/save` | Schreibt ein datiertes Session-Log und erntet automatisch ≤3 Lessons + ≤3 Ideen aus der Sitzung. | Am Ende einer Arbeitssitzung. | Schreibt nach `logs/`, `lessons/`, `ideas/`. |
| `/resume` | Baut den Kontext aus den neuesten Logs neu auf. | Beim Wiedereinstieg ins Projekt. | Liest die neuesten `logs/`. |
| `/lesson` | Hält **eine** Lesson fest (Fehler + Fix + Warum); dedupliziert vorher. | Sobald du etwas gelernt hast. | Liest/schreibt `lessons/` (Dedup-Check zuerst). |
| `/idea` | Hält eine Idee fest: `hook` \| `video` \| `posting` \| `product`. | Wenn dir etwas einfällt. | Schreibt nach `ideas/<kind>/`. |
| `/os` | Dashboard: Stand über alle Projekte (Lessons, Ideen, Hubs, offene Punkte). `/os update` refresht den Auto-Block in `HOME.md`. | Für den Überblick. | Liest den Vault; `update` schreibt `HOME.md`-Block. |
| `/mine-chats` | Destilliert inkrementell Learnings aus importierten Claude-Chat-Transkripten. | Nach neuen Chat-Imports. | Liest `chats/`, schreibt Lessons/Wissen; State-File für Inkrement. |
| `/lessons-gc` | Räumt kalte/veraltete/doppelte Lessons aus. **Löscht nie ohne Rückfrage.** | Zur Pflege, gelegentlich. | Liest `lessons/`; optional ollama-Embeddings für Near-Dubletten. |

### EN

| Command | What it does | When | Reads / Writes |
|---------|-------------|------|----------------|
| `/save` | Writes a dated session log and auto-harvests ≤3 lessons + ≤3 ideas from the session. | At the end of a work session. | Writes to `logs/`, `lessons/`, `ideas/`. |
| `/resume` | Rebuilds context from the newest logs. | When re-entering a project. | Reads the newest `logs/`. |
| `/lesson` | Captures **one** lesson (error + fix + why); dedupes first. | The moment you learn something. | Reads/writes `lessons/` (dedup check first). |
| `/idea` | Captures one idea: `hook` \| `video` \| `posting` \| `product`. | When something comes to mind. | Writes to `ideas/<kind>/`. |
| `/os` | Dashboard: state across all projects (lessons, ideas, hubs, open items). `/os update` refreshes the auto-block in `HOME.md`. | For an overview. | Reads the vault; `update` writes the `HOME.md` block. |
| `/mine-chats` | Incrementally distills learnings from imported Claude chat transcripts. | After new chat imports. | Reads `chats/`, writes lessons/knowledge; state-file for incrementing. |
| `/lessons-gc` | Prunes cold/stale/duplicate lessons. **Never deletes without asking.** | For maintenance, occasionally. | Reads `lessons/`; optional ollama embeddings for near-duplicates. |

---

## 2. Hooks (die Magie / the magic)

Installiert nach / installed to: `~/.claude/hooks/`. Beide sind **rein informativ und
blockieren nie / both are purely informational and never block.**

### DE

| Hook | Typ | Was es tut | Wann | Liest / Schreibt |
|------|-----|-----------|------|------------------|
| `recall-lessons.py` | `UserPromptSubmit` | Lokale semantische Suche (`qmd vsearch`, kein API, $0) über vergangene Lessons; injiziert Treffer in Claudes Kontext, damit dokumentierte Fehler sich nicht wiederholen. | Bei **jedem** Prompt. | Liest den qmd-Index; schreibt ins Fire-Log. |
| `risk-recall.py` | `PreToolUse` | Feuert genau vor riskanten/nach-außen gerichteten Aktionen (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel, `npm publish`, DB drop/delete, Mailversand) und holt relevante Lessons im Moment der Aktion hervor. | **Vor** riskanten Tool-Aufrufen. | Liest den qmd-Index; schreibt ins Fire-Log. |

Beide teilen sich das append-only **Fire-Log** `lesson-fires.jsonl` (im
`PERSONAL_OS_LOG_DIR`). Jeder Treffer wird protokolliert — das treibt die Health-/
Mess-Schleife an.

### EN

| Hook | Type | What it does | When | Reads / Writes |
|------|------|-------------|------|----------------|
| `recall-lessons.py` | `UserPromptSubmit` | Local semantic search (`qmd vsearch`, no API, $0) over past lessons; injects hits into Claude's context so documented mistakes aren't repeated. | On **every** prompt. | Reads the qmd index; appends to the fire-log. |
| `risk-recall.py` | `PreToolUse` | Fires right before risky/outward actions (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel, `npm publish`, db drop/delete, sending mail) and re-surfaces relevant lessons at the action moment. | **Before** risky tool calls. | Reads the qmd index; appends to the fire-log. |

Both share the append-only **fire-log** `lesson-fires.jsonl` (under `PERSONAL_OS_LOG_DIR`).
Every hit is recorded — that powers the health/measure loop.

---

## 3. Engine: `os_lessons.py`

### DE

Die Engine, die der Maintain-Phase Daten liefert. Zwei Unterbefehle:

| Unterbefehl | Was es tut | Genutzt von | Details |
|-------------|-----------|-------------|---------|
| `health` | Kompakte Zusammenfassung des Lesson-Speichers (Anzahl, was feuert, was kalt ist). | `/os` | Liest `lessons/` und das Fire-Log. |
| `gc` | Report über kalte / veraltete / doppelte Lessons. | `/lessons-gc` | Optional ollama-`nomic-embed-text`-Embeddings für die Near-Dubletten-Erkennung. |

`health` ist die Messseite der Recall-Schleife: Es verbindet, was du festgehalten hast,
mit dem, was im Fire-Log tatsächlich gefeuert hat — so siehst du, ob dein Gedächtnis
wirkt. `gc` schlägt nur vor; **gelöscht wird nie ohne Rückfrage** (über `/lessons-gc`).

### EN

The engine that feeds the Maintain phase. Two subcommands:

| Subcommand | What it does | Used by | Details |
|------------|-------------|---------|---------|
| `health` | Compact summary of the lesson store (counts, what fires, what's cold). | `/os` | Reads `lessons/` and the fire-log. |
| `gc` | Report on cold / stale / duplicate lessons. | `/lessons-gc` | Optional ollama `nomic-embed-text` embeddings for near-duplicate detection. |

`health` is the measurement side of the recall loop: it connects what you captured with
what actually fired in the fire-log — so you can see whether your memory is working. `gc`
only proposes; **nothing is deleted without asking** (via `/lessons-gc`).

---

## 4. Auf einen Blick / At a glance

### DE

- **Capture**: `/save`, `/lesson`, `/idea`, `/mine-chats`
- **Recall**: `recall-lessons.py` (jeder Prompt) + `risk-recall.py` (vor Risiko-Aktionen),
  außerdem `/resume`
- **Maintain**: `/os` (+ `os_lessons.py health`), `/lessons-gc` (+ `os_lessons.py gc`)

### EN

- **Capture**: `/save`, `/lesson`, `/idea`, `/mine-chats`
- **Recall**: `recall-lessons.py` (every prompt) + `risk-recall.py` (before risk actions),
  plus `/resume`
- **Maintain**: `/os` (+ `os_lessons.py health`), `/lessons-gc` (+ `os_lessons.py gc`)
