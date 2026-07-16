# Setup / Installation

> **DE zuerst, dann EN.** Each section has a German half and an English half.

Personal OS gibt Claude Code ein dauerhaftes, projektübergreifendes Gedächtnis in
einfachem Markdown — $0, vollständig lokal, ohne API-Key. Diese Anleitung bringt es
in unter 10 Minuten zum Laufen.

Personal OS gives Claude Code a persistent, cross-project memory in plain markdown —
$0, fully local, no API key. This guide gets it running in under 10 minutes.

---

## 1. Voraussetzungen / Prerequisites

### DE

| Was | Pflicht? | Zweck |
|-----|----------|-------|
| macOS oder Linux | ja | Windows nur über WSL |
| Claude Code | ja | das Tool, dem wir das Gedächtnis geben |
| Python 3 | ja | Installer + Engine + Hooks (nur Standardbibliothek) |
| **qmd** | ja (Kern) | semantische Suche = der Recall-Hook |
| **graphify** | optional | Wissensgraph (Struktur-Abfragen) |
| **ollama** | optional | nur für den Dubletten-Pass von `/lessons-gc` |

Personal OS bündelt qmd und graphify **nicht** mit (kein Vendoring). Du installierst
sie selbst — jedes Tool behält seine eigene Lizenz (beide MIT).

### EN

| Thing | Required? | Purpose |
|-------|-----------|---------|
| macOS or Linux | yes | Windows via WSL only |
| Claude Code | yes | the tool we give memory to |
| Python 3 | yes | installer + engine + hooks (stdlib only) |
| **qmd** | yes (core) | semantic search = the recall hook |
| **graphify** | optional | knowledge graph (structure queries) |
| **ollama** | optional | only for the `/lessons-gc` dedup pass |

Personal OS does **not** vendor qmd or graphify. You install them yourself — each keeps
its own license (both MIT).

---

## 2. qmd und graphify installieren / Install qmd and graphify

### DE

**qmd** (Pflicht — die semantische Such-Engine, von Tobi Lutke, MIT):

```bash
npm install -g @tobilu/qmd
```

**graphify** (optional — der Wissensgraph, von Safi Shamsi, MIT):

```bash
uv tool install graphifyy
```

**ollama** (optional — nur für die Near-Dublette-Erkennung in `/lessons-gc`):

```bash
# Installer: siehe https://ollama.com
ollama pull nomic-embed-text
```

Wichtig: qmd lädt beim ersten Lauf lokale GGUF-Modelle und rechnet danach komplett
auf deiner Maschine. Es wird **nie** ein API-Key gesetzt; keine Daten verlassen den
Rechner.

### EN

**qmd** (required — the semantic search engine, by Tobi Lutke, MIT):

```bash
npm install -g @tobilu/qmd
```

**graphify** (optional — the knowledge graph, by Safi Shamsi, MIT):

```bash
uv tool install graphifyy
```

**ollama** (optional — only for near-duplicate detection in `/lessons-gc`):

```bash
# Installer: see https://ollama.com
ollama pull nomic-embed-text
```

Note: qmd downloads local GGUF models on first run and then computes entirely on your
machine. No API key is **ever** set; no data leaves the machine.

Links: qmd → https://github.com/tobi/qmd · graphify → https://github.com/safishamsi/graphify · ollama → https://ollama.com

> **Getestet mit / Tested with:** qmd `2.5.x`, graphify `0.8.x`. Alle Recall-Konsumenten nutzen
> **einen** geteilten Client (`scripts/qmd_search.py`, `qmd vsearch --format json`) — bei einem
> qmd-Major-Update prüfe den Smoke-Test (`python3 install/doctor.py`), falls Recall verstummt. /
> All recall consumers go through **one** shared client (`scripts/qmd_search.py`,
> `qmd vsearch --format json`); if a future qmd release changes that contract and recall goes
> quiet, the doctor's smoke test will catch it.

---

## 3. Klonen und installieren / Clone and install

### DE

```bash
git clone <repo> && cd personal-os && ./install/install.sh
```

`install.sh` ist ein dünner Wrapper um `python3 install/install.py` (reine
Standardbibliothek — keine pip-Abhängigkeiten). Das Skript ist idempotent: ein
zweiter Lauf überschreibt deine bestehende Config nicht.

**Vault woanders ablegen?** Standard ist `~/vault`. Verschieben per:

```bash
./install/install.sh --vault-path /pfad/zu/meinem/vault
```

### EN

```bash
git clone <repo> && cd personal-os && ./install/install.sh
```

`install.sh` is a thin wrapper around `python3 install/install.py` (pure stdlib — no pip
dependencies). The script is idempotent: a second run won't clobber your existing config.

**Want the vault elsewhere?** Default is `~/vault`. Relocate with:

```bash
./install/install.sh --vault-path /path/to/my/vault
```

---

## 4. Was der Installer tut / What the installer does

### DE

1. **Erstellt `~/vault`** aus dem mitgelieferten Scaffold (Ordnerbaum, `CLAUDE.md`,
   `HOME.md`, `_templates/`). Existiert der Vault schon, bleibt er unangetastet.
2. **Merged Hooks, Commands und Skills nach `~/.claude/`** — ohne deine bestehende
   `settings.json` zu zerstören. Vorhandene Einträge bleiben erhalten; Personal OS
   fügt nur seine eigenen hinzu.
3. **Schreibt `~/.config/qmd/index.yml`** so, dass qmd den Vault indiziert.
4. **Führt den ersten `qmd embed` aus** — baut den semantischen Index, damit Recall
   ab dem ersten Prompt funktioniert.
5. **Setzt Env-Variablen** in `settings.json` → `env` (siehe Tabelle unten).
6. **Optional: nächtlicher graphify-Rebuild** über `launchd` (macOS) bzw. `cron`
   (Linux), damit der Graph aktuell bleibt (`--schedule`, 04:15) — und **optional der
   nächtliche Dreaming-Pass** (`--schedule-dream`, 04:45 — ~30 Minuten nach dem Graph-Rebuild, niedrige Prozess-Priorität). Siehe `docs/COMMANDS.md` §3c.
7. **Schreibt ein Install-Manifest** (`install-manifest.json` im State-Home) — damit
   `install.py --check-drift` später „lokal angepasst" von „Update verfügbar"
   unterscheiden kann.

**Env-Variablen, die der Installer setzt:**

| Variable | Default | Zweck |
|----------|---------|-------|
| `PERSONAL_OS_VAULT` | `~/vault` | Speicherort des Vaults |
| `PERSONAL_OS_OLLAMA` | `http://localhost:11434` | lokaler ollama-Endpunkt (optional) |
| `PERSONAL_OS_LOG_DIR` | XDG-State-Dir / `~/.local/state/personal-os/logs` (macOS evtl. `~/Library/Logs`) | Fire-Log & Diagnose |
| `PERSONAL_OS_LANG` | `en` (auch `de`) | Sprache der Hook-/Command-Oberfläche |
| `PERSONAL_OS_DREAM_MODEL` | `llama3.2:3b` | Generierungsmodell für den optionalen Dreaming-Pass |

### EN

1. **Creates `~/vault`** from the bundled scaffold (directory tree, `CLAUDE.md`,
   `HOME.md`, `_templates/`). If the vault already exists, it is left untouched.
2. **Merges hooks, commands, and skills into `~/.claude/`** — without clobbering your
   existing `settings.json`. Existing entries are preserved; Personal OS only adds its
   own.
3. **Writes `~/.config/qmd/index.yml`** so qmd indexes the vault.
4. **Runs the first `qmd embed`** — builds the semantic index so recall works from your
   very first prompt.
5. **Sets env vars** in `settings.json` → `env` (see table below).
6. **Optional: nightly graphify rebuild** via `launchd` (macOS) or `cron` (Linux), so
   the graph stays current (`--schedule`, 04:15) — and **optionally the nightly
   dreaming pass** (`--schedule-dream`, 04:45 — ~30 minutes after the graph rebuild, low process priority). See `docs/COMMANDS.md` §3c.
7. **Writes an install manifest** (`install-manifest.json` in the state home) — so
   `install.py --check-drift` can later tell "locally customized" apart from
   "update available".

**Env vars the installer sets:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `PERSONAL_OS_VAULT` | `~/vault` | vault location |
| `PERSONAL_OS_OLLAMA` | `http://localhost:11434` | local ollama endpoint (optional) |
| `PERSONAL_OS_LOG_DIR` | XDG state dir / `~/.local/state/personal-os/logs` (macOS may use `~/Library/Logs`) | fire-log & diagnostics |
| `PERSONAL_OS_LANG` | `en` (also `de`) | language of the hook/command UI |
| `PERSONAL_OS_DREAM_MODEL` | `llama3.2:3b` | generation model for the optional dreaming pass |

---

## 5. Smoke-Test beim ersten Start / First-run smoke test

### DE

So prüfst du in 30 Sekunden, dass der Recall-Hook lebt:

1. Öffne Claude Code in **irgendeinem** Projekt.
2. Tippe einen Prompt, der zu einer der mitgelieferten Beispiel-Lessons passt —
   z. B. etwas über einen `git push --force` auf einen geteilten Branch.
3. Beobachte, wie der `recall-lessons.py`-Hook (`UserPromptSubmit`) die passende
   vergangene Lesson **in Claudes Kontext injiziert**, bevor Claude antwortet.

Siehst du die eingespielte Lesson, läuft die Recall-Schleife. (Der Hook blockiert
nie — er ist rein informativ.)

### EN

A 30-second check that the recall hook is alive:

1. Open Claude Code in **any** project.
2. Type a prompt that matches one of the seeded example lessons — e.g. something about a
   `git push --force` on a shared branch.
3. Watch the `recall-lessons.py` hook (`UserPromptSubmit`) **inject the matching past
   lesson into Claude's context** before Claude answers.

If you see the injected lesson, the recall loop is working. (The hook never blocks — it's
purely informational.)

---

## 5b. ChatGPT-Historie importieren / Import your ChatGPT history

### DE

Dein ChatGPT-Verlauf enthält oft jahrelange Substanz (Strategie, Recherche, Ideen) — Personal OS
kann ihn als Mining-Quelle erschließen. Der Import ist **manuell, einmalig pro Export, 100 % lokal**:

1. Export anfordern: chatgpt.com → Settings → Data controls → **Export data**. Du bekommst
   eine Zip-Datei per Mail (oft 1–2 GB).
2. Trockenlauf, dann Import (liest die JSON-Shards direkt aus der Zip — kein Entpacken nötig):
   ```bash
   python3 ~/.personal-os/scripts/chatgpt_to_obsidian.py --zip ~/Downloads/<export>.zip --dry-run
   python3 ~/.personal-os/scripts/chatgpt_to_obsidian.py --zip ~/Downloads/<export>.zip
   ```
   Eine Markdown-Note pro Conversation landet in `<vault>/chats/gpt/` (Tagging rule-based, $0).
   Inkrementell: ein erneuter Lauf gegen einen neueren Export schreibt nur das Delta.
3. Destillieren: `/mine-chats` verarbeitet `chats/code/` **und** `chats/gpt/` in Batches
   (Default 10) — nur das übertragbare Gold wird zu Lessons/Knowledge/Ideen/Profile-Notizen.

**Privacy:** ChatGPT-Verläufe sind oft persönlicher als Coding-Transkripte (Gesundheit, Finanzen).
Das Vault-Scaffold gitignored deshalb `chats/` **komplett** (ebenso `_inbox/`) — Roh-Importe
erreichen nie ein Remote; versioniert werden nur die destillierten, von dir promoteten Notizen.

### EN

Your ChatGPT history often holds years of substance (strategy, research, ideas) — Personal OS can
tap it as a mining source. The import is **manual, one-off per export, 100% local**:

1. Request the export: chatgpt.com → Settings → Data controls → **Export data**. You'll get a
   zip by mail (often 1–2 GB).
2. Dry-run, then import (reads the JSON shards straight out of the zip — no extraction needed):
   ```bash
   python3 ~/.personal-os/scripts/chatgpt_to_obsidian.py --zip ~/Downloads/<export>.zip --dry-run
   python3 ~/.personal-os/scripts/chatgpt_to_obsidian.py --zip ~/Downloads/<export>.zip
   ```
   One markdown note per conversation lands in `<vault>/chats/gpt/` (rule-based tagging, $0).
   Incremental: re-running against a newer export writes only the delta.
3. Distill: `/mine-chats` processes `chats/code/` **and** `chats/gpt/` in batches (default 10) —
   only the transferable gold becomes lessons/knowledge/idea/profile notes.

**Privacy:** ChatGPT history is often more personal than coding transcripts (health, finances).
The vault scaffold therefore gitignores `chats/` **entirely** (and `_inbox/` too) — raw imports
never reach a remote; only the distilled notes you promote get versioned.

---

## 5c. Vault-Autopush einrichten / Set up vault autopush

### DE

Opt-in: Am Ende jeder Claude-Code-Session (Stop-Hook) und im Nightly wird der Vault committet und
in **sein eigenes privates** Remote gepusht — Backup binnen Sekunden statt „irgendwann".

**Voraussetzung:** Der Vault ist ein Git-Repo mit Remote (der Installer richtet das bewusst
NICHT ein — das Remote ist deine Entscheidung):

```bash
cd ~/vault
git init
git remote add origin git@github.com:<you>/<private-vault-repo>.git   # PRIVAT!
```

Dann beim (Re-)Install aktivieren:

```bash
./install/install.sh --autopush
```

**Sicherheitsmodell:** `vault_autopush.sh` staged per **Allowlist** (lessons, knowledge, ideas,
projects, profile, permanent, logs, `_templates`, `_archive` + Top-Level-`*.md`) statt `git add -A`
— eine Denylist fällt bei jedem neuen sensiblen Ordner offen, die Allowlist fällt zu. Belt &
braces: landet doch etwas aus `chats/` oder `_inbox/` im Index, bricht der Sync ab, committet
nichts. Ohne Remote ist das Skript ein stiller No-op. Deaktivieren: Re-Install ohne `--autopush`
oder die Stop-Hook-Gruppe aus `settings.json` entfernen.

### EN

Opt-in: at the end of every Claude Code session (Stop hook) and in the nightly, the vault is
committed and pushed to **its own private** remote — backup within seconds instead of "someday".

**Prerequisite:** the vault is a git repo with a remote (the installer deliberately does NOT set
this up — the remote is your call):

```bash
cd ~/vault
git init
git remote add origin git@github.com:<you>/<private-vault-repo>.git   # PRIVATE!
```

Then enable at (re-)install time:

```bash
./install/install.sh --autopush
```

**Security model:** `vault_autopush.sh` stages via an **allowlist** (lessons, knowledge, ideas,
projects, profile, permanent, logs, `_templates`, `_archive` + top-level `*.md`) instead of
`git add -A` — a denylist fails open on every new sensitive folder, the allowlist fails closed.
Belt and braces: if anything from `chats/` or `_inbox/` still ends up in the index, the sync
aborts and commits nothing. Without a remote the script is a silent no-op. Disable: re-install
without `--autopush`, or remove the Stop-hook group from `settings.json`.

---

## 6. Deinstallieren / Uninstall

### DE

```bash
python3 install/uninstall.py
```

Entfernt die von Personal OS hinzugefügten Hooks/Commands/Skills aus `~/.claude/` und
seine Env-Einträge. **Dein Vault wird nicht gelöscht** — deine Notizen gehören dir.

### EN

```bash
python3 install/uninstall.py
```

Removes the Personal OS hooks/commands/skills it added to `~/.claude/` and its env
entries. **Your vault is not deleted** — your notes are yours.

---

## 7. Fehlersuche / Troubleshooting

### DE

```bash
python3 install/doctor.py
```

`doctor.py` prüft die häufigsten Stolperfallen: ist qmd installiert und auf dem PATH,
existiert der Vault, ist `index.yml` geschrieben, wurde ein `qmd embed` ausgeführt, sind
die Hooks in `settings.json` registriert, und (optional) sind graphify/ollama erreichbar.
Ausgabe ist eine Checkliste mit konkreten Fix-Hinweisen.

> **Zwei Doctors:** `install/doctor.py` ist der einmalige **Post-Install**-Check (läuft eine echte
> Recall-Abfrage). Für die **laufende** Gesundheit eines aktiven OS — feuern die Hooks noch, ist die
> Harvest-Queue/Inbox abgearbeitet, verrotten Lessons — nutze `/os doctor` (läuft auch nächtlich).

**Häufige Fälle:**
- *Recall feuert nicht* → erst `qmd vsearch "test"` von Hand laufen lassen; liefert es
  nichts, fehlt vermutlich der erste `qmd embed`.
- *graphify-Befehle fehlen* → optional; ohne graphify funktioniert alles außer den
  Struktur-Abfragen.
- *`/lessons-gc` findet keine Near-Dubletten* → ollama + `nomic-embed-text` optional
  nachinstallieren.

### EN

```bash
python3 install/doctor.py
```

`doctor.py` checks the most common pitfalls: is qmd installed and on PATH, does the vault
exist, is `index.yml` written, has a `qmd embed` run, are the hooks registered in
`settings.json`, and (optionally) are graphify/ollama reachable. Output is a checklist
with concrete fix hints.

> **Two doctors:** `install/doctor.py` is the one-time **post-install** check (it runs a real recall
> query). For the **ongoing** health of a live OS — are the hooks still firing, is the harvest
> queue/inbox drained, are lessons rotting — use `/os doctor` (also runs nightly).

**Common cases:**
- *Recall doesn't fire* → run `qmd vsearch "test"` by hand first; if it returns nothing,
  you're probably missing the initial `qmd embed`.
- *graphify commands missing* → optional; everything except structure queries works
  without graphify.
- *`/lessons-gc` finds no near-duplicates* → optionally add ollama + `nomic-embed-text`.

---

**Reminder / Erinnerung:** ollama is **optional** — Personal OS works fully without it;
it only powers the near-duplicate pass in `/lessons-gc`.
