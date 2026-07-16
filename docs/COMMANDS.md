# Commands & Hooks Reference / Befehls- & Hook-Referenz

> **DE zuerst, dann EN.** Each section has a German half and an English half.

Vollständige Referenz: die 10 Slash-Commands, die 3 Hooks, die Engines `os_lessons.py` /
`os_doctor.py` (+ optional `dream.py`) und die Wartungs-Skripte — was jedes tut, wann es
läuft, was es liest/schreibt.

Complete reference: the 10 slash commands, the 3 hooks, the engines (`os_lessons.py`,
`os_doctor.py`, + optional `dream.py`), and the maintenance scripts — what each does,
when it runs, what it reads/writes.

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
| `/os` | Dashboard: Stand über alle Projekte (Lessons, Ideen, Hubs, offene Punkte). `/os update` refresht den Auto-Block in `HOME.md`; `/os doctor` fährt den Self-Health-Check. | Für den Überblick. | Liest den Vault; `update` schreibt `HOME.md`-Block. |
| `/mine-chats` | Destilliert inkrementell Learnings aus importierten Claude-Chat-Transkripten. | Nach neuen Chat-Imports. | Liest `chats/`, schreibt Lessons/Wissen; State-File für Inkrement. |
| `/lessons-gc` | Räumt kalte/veraltete/doppelte Lessons aus. **Löscht nie ohne Rückfrage.** | Zur Pflege, gelegentlich. | Liest `lessons/`; optional ollama-Embeddings für Near-Dubletten. |
| `/harvest` | Verarbeitet die Auto-Harvest-Queue: destilliert Lessons/Ideen aus Sessions, die **ohne `/save`** endeten, in die Review-Inbox `_inbox/`. | Wenn die Queue gefüllt ist (`/os doctor` zeigt's). | Liest Queue + Transkripte; schreibt Drafts nach `_inbox/`. |
| `/dream` | Zeigt die neueste nächtliche Traumnotiz; `/dream review` geht die Vorschläge risk-getiert durch (trivial Umkehrbares automatisch, Inhaltsänderungen per Y/N) und führt Angenommenes über die bestehenden Wege aus. | Morgens, wenn Dreaming geplant ist. | Liest `_inbox/dreams/`; `review` schreibt Wikilinks + Feedback nach `dream-feedback.jsonl` (adaptive Schwellwerte). |
| `/producer` | Zeigt wartende Cold-Outreach-Textentwürfe (aus dem `producer`-Pass); `/producer review` legt nach Y/N ECHTE Gmail-Drafts an — nie automatisch, nie gesendet. | Optional, wenn du `producer-queue.jsonl` selbst befüllst. | Liest `_inbox/producer-drafts/`; `review` legt Gmail-Drafts an + schreibt `producer-feedback.jsonl`. |

### EN

| Command | What it does | When | Reads / Writes |
|---------|-------------|------|----------------|
| `/save` | Writes a dated session log and auto-harvests ≤3 lessons + ≤3 ideas from the session. | At the end of a work session. | Writes to `logs/`, `lessons/`, `ideas/`. |
| `/resume` | Rebuilds context from the newest logs. | When re-entering a project. | Reads the newest `logs/`. |
| `/lesson` | Captures **one** lesson (error + fix + why); dedupes first. | The moment you learn something. | Reads/writes `lessons/` (dedup check first). |
| `/idea` | Captures one idea: `hook` \| `video` \| `posting` \| `product`. | When something comes to mind. | Writes to `ideas/<kind>/`. |
| `/os` | Dashboard: state across all projects (lessons, ideas, hubs, open items). `/os update` refreshes the auto-block in `HOME.md`; `/os doctor` runs the self-health check. | For an overview. | Reads the vault; `update` writes the `HOME.md` block. |
| `/mine-chats` | Incrementally distills learnings from imported Claude chat transcripts. | After new chat imports. | Reads `chats/`, writes lessons/knowledge; state-file for incrementing. |
| `/lessons-gc` | Prunes cold/stale/duplicate lessons. **Never deletes without asking.** | For maintenance, occasionally. | Reads `lessons/`; optional ollama embeddings for near-duplicates. |
| `/harvest` | Processes the auto-harvest queue: distills lessons/ideas from sessions that ended **without `/save`** into the review inbox `_inbox/`. | When the queue has items (`/os doctor` shows it). | Reads the queue + transcripts; writes drafts to `_inbox/`. |
| `/dream` | Shows the latest overnight dream note; `/dream review` walks its suggestions risk-tiered (trivially-reversible ones automatic, content changes per Y/N) and executes accepted ones through the existing commands. | Mornings, if dreaming is scheduled. | Reads `_inbox/dreams/`; `review` writes wikilinks + feedback to `dream-feedback.jsonl` (adaptive thresholds). |
| `/producer` | Shows pending cold-outreach text drafts (from the `producer` pass); `/producer review` creates REAL Gmail drafts after a yes/no — never automatically, never sent. | Optional, once you populate `producer-queue.jsonl` yourself. | Reads `_inbox/producer-drafts/`; `review` creates Gmail drafts + writes `producer-feedback.jsonl`. |

---

## 2. Hooks (die Magie / the magic)

Installiert nach / installed to: `~/.claude/hooks/`. Beide sind **rein informativ und
blockieren nie / both are purely informational and never block.**

### DE

| Hook | Typ | Was es tut | Wann | Liest / Schreibt |
|------|-----|-----------|------|------------------|
| `recall-lessons.py` | `UserPromptSubmit` | Lokale semantische Suche (`qmd vsearch`, kein API, $0) über vergangene Lessons; injiziert Treffer in Claudes Kontext, damit dokumentierte Fehler sich nicht wiederholen. | Bei **jedem** Prompt. | Liest den qmd-Index; schreibt ins Fire-Log. |
| `risk-recall.py` | `PreToolUse` | Feuert genau vor riskanten/nach-außen gerichteten Aktionen (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel, `npm publish`, DB drop/delete, Mailversand) und holt relevante Lessons im Moment der Aktion hervor. | **Vor** riskanten Tool-Aufrufen. | Liest den qmd-Index; schreibt ins Fire-Log. |
| `health-sentinel.py` | `SessionStart` | Backstop für „der Scheduler selbst ist tot": liest `health.json` und meldet Degradierung/Stille der Nightly-Jobs max. 1×/Tag als systemMessage; wärmt zusätzlich das qmd-Embedding-Modell detached vor (kein Cold-Start-Timeout beim ersten Recall). | Beim Session-Start. | Liest `health.json`; schreibt einen Tages-Marker nach `$TMPDIR`. |

Die Recall-Hooks teilen sich das append-only **Fire-Log** `lesson-fires.jsonl` (im
`PERSONAL_OS_HOME`, Default `~/.claude/personal-os/`). Protokolliert werden Treffer
**und Misses** (`type`: `hit`/`zero`/`timeout`/`error`/`no_qmd`) — das treibt die
Health-/Mess-Schleife an und macht Coverage-Lücken sichtbar.

### EN

| Hook | Type | What it does | When | Reads / Writes |
|------|------|-------------|------|----------------|
| `recall-lessons.py` | `UserPromptSubmit` | Local semantic search (`qmd vsearch`, no API, $0) over past lessons; injects hits into Claude's context so documented mistakes aren't repeated. | On **every** prompt. | Reads the qmd index; appends to the fire-log. |
| `risk-recall.py` | `PreToolUse` | Fires right before risky/outward actions (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel, `npm publish`, db drop/delete, sending mail) and re-surfaces relevant lessons at the action moment. | **Before** risky tool calls. | Reads the qmd index; appends to the fire-log. |
| `health-sentinel.py` | `SessionStart` | Backstop for "the scheduler itself is dead": reads `health.json` and reports nightly-job degradation/silence at most once per day as a systemMessage; also warms the qmd embedding model detached (no cold-start timeout on the first recall). | On session start. | Reads `health.json`; writes a daily marker to `$TMPDIR`. |

The recall hooks share the append-only **fire-log** `lesson-fires.jsonl` (under
`PERSONAL_OS_HOME`, default `~/.claude/personal-os/`). Hits **and misses** are recorded
(`type`: `hit`/`zero`/`timeout`/`error`/`no_qmd`) — that powers the health/measure loop
and makes coverage gaps visible.

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

## 3b. Runtime-Doctor: `os_doctor.py` / Runtime doctor: `os_doctor.py`

### DE

Deterministischer Self-Health-Check ($0, read-only): feuern die Recall-Hooks, ist der qmd-Index
frisch, verrotten Lessons, ist die Harvest-Queue/Inbox abgearbeitet. Läuft via **`/os doctor`** und
nächtlich aus `graph_rebuild.sh`. Exit 1 nur bei echtem FAIL; Optionales (Scheduler, Vault-git)
degradiert zu INFO. Nutzt `os_lessons.analyze` wieder. **Verschieden von `install/doctor.py`**
(dem einmaligen Post-Install-Smoke-Test).

### EN

Deterministic self-health check ($0, read-only): are the recall hooks firing, is the qmd index fresh,
are lessons rotting, is the harvest queue/inbox drained. Runs via **`/os doctor`** and nightly from
`graph_rebuild.sh`. Exit 1 only on a real FAIL; optional features (scheduler, vault git) degrade to
INFO. Reuses `os_lessons.analyze`. **Distinct from `install/doctor.py`** (the one-time post-install
smoke test).

---

## 3c. Optional: Dreaming — `dream.py` / `dream_run.sh`

### DE

Optionaler dritter Nightly-Job, registrierbar via `install.py --schedule-dream` (Ollama
empfohlen — ohne es laufen nur die LLM-freien Pässe). Läuft ~30 Minuten nach dem
Graph-Rebuild und arbeitet sieben Analyse-Pässe plus den Report ab (Feuer-Muster,
Producer, implizite Verbindungen, Lesson-Konsolidierung, Venture-Muster, Inbox-Triage,
Tagesrest-Digest) — alle außer Tagesrest sind reine Embedding-/Python-Pässe ohne
Pflicht-LLM. Schreibt **ausschließlich** eine Vorschlags-Notiz nach `_inbox/dreams/`,
ändert nie selbst eine Notiz. Aus/An: Datei `dream.off` im Engine-Home-Verzeichnis.
Review via **`/dream review`**.

**Venture-Muster** (`ventures`): sobald ein neuer Projekt-Hub auftaucht (jung genug,
21-Tage-Fenster), wird er gegen deine eigenen `done`/`parked`-Projekte auf Ähnlichkeit
geprüft — mit einem transitiven Check (die "toten Geschwister" müssen sich auch
UNTEREINANDER ähneln), damit zwei zufällig nahe, aber unabhängige Projekte nicht als
"Muster" gelten. **Kalibriere den Threshold an deinem eigenen Vault** — Cosine-Werte für
Business-Prosa variieren mit deinem Schreibstil; siehe Kommentar bei `VENTURES_MIN_THRESHOLD`
in `dream.py`.

**Producer** (`producer`): rendert reinen Template-Text aus einer von dir befüllten
`producer-queue.jsonl` (Pflichtfelder `id`, `observation`/`pain_point` — `id` identifiziert
den Eintrag für die Warteschlangen-Bereinigung nach dem Rendern, `observation`/`pain_point`
MÜSSEN von dir kommen, niemals vom Pass erfunden) nach `_inbox/producer-drafts/`. **Kein LLM-Call** — nur
`str.format()` gegen `producer-templates.json` (Beispiele: `config/producer-*.example.*`).
Da `dream.py` als Cron-Skript ohne MCP-Zugriff läuft, entstehen echte Gmail-Entwürfe
ausschließlich über **`/producer review`**.

### EN

Optional third nightly job, registered via `install.py --schedule-dream` (Ollama
recommended — without it only the LLM-free passes run). Runs ~30 minutes after the
graph rebuild and works through seven analysis passes plus the report (firing
patterns, producer, implicit connections, lesson consolidation, venture patterns,
inbox triage, day-residue digest) — all but residue are embeddings/Python only, no
mandatory LLM. Writes **only** a suggestions note to `_inbox/dreams/`; never edits a
note itself. On/off: a `dream.off` file in the engine's home dir. Review via
**`/dream review`**.

**Venture patterns** (`ventures`): whenever a new project hub appears (young enough,
21-day window), it's checked for similarity against your own `done`/`parked` projects —
with a transitive check (the "dead siblings" must also resemble EACH OTHER), so two
projects that happen to land near the candidate but have nothing to do with each other
don't get reported as "a pattern". **Calibrate the threshold against your own vault** —
cosine scores for business prose vary with your writing style; see the comment next to
`VENTURES_MIN_THRESHOLD` in `dream.py`.

**Producer** (`producer`): renders pure template text from a `producer-queue.jsonl` you
fill in yourself (required fields `id`, `observation`/`pain_point` — `id` identifies the
entry so it can be cleared from the queue once rendered, `observation`/`pain_point` MUST
come from you, never invented by the pass) into `_inbox/producer-drafts/`. **No LLM call** — just
`str.format()` against `producer-templates.json` (examples: `config/producer-*.example.*`).
Since `dream.py` runs as a cron script with no MCP access, real Gmail drafts are only
ever created via **`/producer review`**.

---

## 4. Wartungs-Skripte / Maintenance scripts

Installiert nach / installed to: `~/.personal-os/scripts/` (bzw. dein `scripts_dir`).

### DE

| Skript | Was es tut | Wann | Details |
|--------|-----------|------|---------|
| `graph_rebuild.sh` | Nightly-Wartung: optionaler Chat-Import, graphify-Update + Wikilink-Injektion, qmd-Re-Index, Fire-Log-Rotation, Vault-Snapshot (via `vault_autopush.sh`), Runtime-Doctor. | Nächtlich 04:15 (`--schedule`). | mkdir-Lock; jeder Step meldet rc/Dauer an `pos_health.py` → `health.json`. Fail-open. |
| `dream_run.sh` | Orchestriert die Dreaming-Pässe (Kill-Switch, RAM-Pre-Flight, Kollisions-Guard gegen den Graph-Rebuild, Timeouts), entlädt die Modelle danach. | Nächtlich 04:45 (`--schedule-dream`). | mkdir-Lock + Health-Steps (Job `dream`); Early-Exits finalisieren die Health-Datei trotzdem. |
| `vault_autopush.sh` | Committet + pusht den Vault in **sein eigenes** privates Remote — **Allowlist-Staging** (nur kuratierte Ordner + Top-Level-`*.md`; `chats/` + `_inbox/` können strukturell nie gestaged werden). | Opt-in Stop-Hook (`--autopush`) **und** aus dem Nightly — ein Codepfad. | Lock `vault-git`, Commit-rc-Check, Abort bei sensiblen Pfaden im Index, WARN bei Strays. No-op ohne Vault-Git-Repo. |
| `pos_health.py` | Health-Signal der Nightly-Jobs: `begin`/`step`/`finalize` spiegeln jeden Step-rc nach `health.json`; `check` = Einzeiler + Exit 1 bei Degradierung. | Von den Wrappern aufgerufen. | Max. 1 Desktop-Notification pro Tag (Debounce). |
| `qmd_search.py` / `pos_utils.py` | Geteilte Fundamente: **der eine** qmd-Client (`vsearch --format json`, Score 0–100) bzw. atomare Writes, mkdir-Locks, Fire-Log. | Von Hooks, Dream-Engine, Doctors importiert. | Ersetzt vier divergierte qmd-Parser. |

### EN

| Script | What it does | When | Details |
|--------|-------------|------|---------|
| `graph_rebuild.sh` | Nightly maintenance: optional chat import, graphify update + wikilink injection, qmd re-index, fire-log rotation, vault snapshot (via `vault_autopush.sh`), runtime doctor. | Nightly 04:15 (`--schedule`). | mkdir lock; every step reports rc/duration to `pos_health.py` → `health.json`. Fail-open. |
| `dream_run.sh` | Orchestrates the dreaming passes (kill switch, RAM pre-flight, collision guard against the graph rebuild, timeouts), unloads the models afterwards. | Nightly 04:45 (`--schedule-dream`). | mkdir lock + health steps (job `dream`); early exits still finalize the health file. |
| `vault_autopush.sh` | Commits + pushes the vault to **its own** private remote — **allowlist staging** (only curated folders + top-level `*.md`; `chats/` + `_inbox/` structurally can never be staged). | Opt-in Stop hook (`--autopush`) **and** from the nightly — one code path. | Lock `vault-git`, commit-rc check, abort on sensitive paths in the index, WARN on strays. No-op without a vault git repo. |
| `pos_health.py` | Health signal for the nightly jobs: `begin`/`step`/`finalize` mirror every step rc into `health.json`; `check` = one-liner + exit 1 when degraded. | Called by the wrappers. | At most one desktop notification per day (debounce). |
| `qmd_search.py` / `pos_utils.py` | Shared foundations: **the one** qmd client (`vsearch --format json`, score 0–100) resp. atomic writes, mkdir locks, fire-log. | Imported by hooks, dream engine, doctors. | Replaces four divergent qmd parsers. |

---

## 5. Auf einen Blick / At a glance

### DE

- **Capture**: `/save`, `/lesson`, `/idea`, `/mine-chats`, `/harvest` (un-gesavte Sessions)
- **Recall**: `recall-lessons.py` (jeder Prompt) + `risk-recall.py` (vor Risiko-Aktionen),
  außerdem `/resume`
- **Maintain / Self-Heal**: `/os` (+ `os_lessons.py health`), `/os doctor` (+ `os_doctor.py`),
  `/lessons-gc` (+ `os_lessons.py gc`), `/dream` (+ nächtliche Dreaming-Engine),
  `health-sentinel.py` + `pos_health.py` (Nightly-Gesundheit), `vault_autopush.sh` (Backup)

### EN

- **Capture**: `/save`, `/lesson`, `/idea`, `/mine-chats`, `/harvest` (un-saved sessions)
- **Recall**: `recall-lessons.py` (every prompt) + `risk-recall.py` (before risk actions),
  plus `/resume`
- **Maintain / self-heal**: `/os` (+ `os_lessons.py health`), `/os doctor` (+ `os_doctor.py`),
  `/lessons-gc` (+ `os_lessons.py gc`), `/dream` (+ the nightly dreaming engine),
  `health-sentinel.py` + `pos_health.py` (nightly health), `vault_autopush.sh` (backup)
