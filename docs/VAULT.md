# Vault Reference / Vault-Referenz

> **DE zuerst, dann EN.** Each section has a German half and an English half.

Der Vault ist dein Gedächtnis: ein Obsidian-artiger Markdown-Ordner, standardmäßig unter
`~/vault`. Dieses Dokument ist die Strukturreferenz — Ordnerbaum, Frontmatter-Schema,
Regeln, Notiztypen und Templates.

The vault is your memory: an Obsidian-style markdown folder, by default at `~/vault`. This
document is the structure reference — directory tree, frontmatter schema, rules, note
types, and templates.

---

## 1. Ordnerbaum / Directory tree

### DE

```
~/vault/
├── CLAUDE.md            # Regeln für Claude in jedem Projekt
├── HOME.md              # Einstieg + Auto-Block (von /os update gepflegt)
├── _templates/         # Vorlagen für neue Notizen
├── lessons/            # Fehler + Fix + Warum (das Herz des Recall)
├── ideas/
│   ├── hooks/          # Hook-Ideen
│   ├── video/          # Video-Ideen
│   ├── posting/        # Posting-Ideen
│   └── product/        # Produkt-Ideen
├── knowledge/
│   ├── coding/
│   ├── design/
│   ├── marketing/
│   └── business/
├── projects/           # Projekt-Hubs (eine Note pro Projekt)
├── profile/            # deine Standards/Vorlieben (Design, Stil, Ansprüche)
├── logs/               # datierte Session-Logs (/save)
├── permanent/          # langlebige, kuratierte Evergreen-Notizen
├── _inbox/             # Harvest-Drafts (status: draft) — außerhalb der qmd-Collection, nicht im Recall
└── chats/
    ├── code/           # importierte Claude-Code-Transkripte
    └── web/            # importierte Web-Chat-Transkripte
```

### EN

```
~/vault/
├── CLAUDE.md            # rules for Claude in every project
├── HOME.md              # entry point + auto-block (maintained by /os update)
├── _templates/         # templates for new notes
├── lessons/            # error + fix + why (the heart of recall)
├── ideas/
│   ├── hooks/          # hook ideas
│   ├── video/          # video ideas
│   ├── posting/        # posting ideas
│   └── product/        # product ideas
├── knowledge/
│   ├── coding/
│   ├── design/
│   ├── marketing/
│   └── business/
├── projects/           # project hubs (one note per project)
├── profile/            # your standards/preferences (design, style, bar)
├── logs/               # dated session logs (/save)
├── permanent/          # long-lived, curated evergreen notes
├── _inbox/             # harvest drafts (status: draft) — outside the qmd collection, not in recall
└── chats/
    ├── code/           # imported Claude Code transcripts
    └── web/            # imported web-chat transcripts
```

---

## 2. YAML-Frontmatter-Schema / YAML frontmatter schema

### DE

**Frontmatter ist Pflicht** in jeder Note. Pflichtfelder oben, optionale darunter.

| Feld | Pflicht? | Werte / Bedeutung |
|------|----------|-------------------|
| `kind` | ja | Notiztyp: `lesson` · `idea` · `knowledge` · `project-hub` · `decision` · `profile` · `log` · `permanent` |
| `domain` | ja | Sachgebiet: `coding` · `design` · `marketing` · `business` |
| `status` | ja | z. B. `active` · `archived` · `draft` |
| `project` | optional | zugehöriges Projekt (für projektbezogene Notizen) |
| `confidence` | optional | wie sicher: `low` · `medium` · `high` |
| `source` | optional | Herkunft (z. B. Chat-Import, URL, Session) |
| `review_by` | optional | Datum, an dem die Note re-validiert werden soll |

Beispiel:

```yaml
---
kind: lesson
domain: coding
status: active
project: personal-os
confidence: high
source: session-2026-06-23
review_by: 2026-12-23
---
```

### EN

**Frontmatter is mandatory** on every note. Required fields first, optional below.

| Field | Required? | Values / meaning |
|-------|-----------|------------------|
| `kind` | yes | note type: `lesson` · `idea` · `knowledge` · `project-hub` · `decision` · `profile` · `log` · `permanent` |
| `domain` | yes | subject area: `coding` · `design` · `marketing` · `business` |
| `status` | yes | e.g. `active` · `archived` · `draft` |
| `project` | optional | associated project (for project-scoped notes) |
| `confidence` | optional | how sure: `low` · `medium` · `high` |
| `source` | optional | provenance (e.g. chat import, URL, session) |
| `review_by` | optional | date the note should be re-validated |

Example:

```yaml
---
kind: lesson
domain: coding
status: active
project: personal-os
confidence: high
source: session-2026-06-23
review_by: 2026-12-23
---
```

---

## 3. Regeln: Wikilinks & Dateinamen / Rules: wikilinks & filenames

### DE

- **Dateinamen in kebab-case**: `never-force-push-a-shared-branch.md`, nicht
  `Never_Force_Push.md`.
- **`[[wikilinks]]`**: mindestens **2 pro Note**. Links machen aus losen Notizen einen
  Graphen — und füttern graphify.
- **Bilingual schreiben, wo es zählt**: Notizen, die du später beiden Sprachen zugänglich
  machen willst, ruhig DE+EN halten (Recall findet sie ohnehin sprachübergreifend).
- **Nie ohne Rückfrage löschen**: Notizen werden nicht still entfernt — `/lessons-gc`
  fragt immer.
- **In Lessons gilt**: ein `## Fix` muss **verifiziert** sein; gescheiterte Versuche
  gehören unter `## Was NICHT funktioniert`.

### EN

- **Filenames in kebab-case**: `never-force-push-a-shared-branch.md`, not
  `Never_Force_Push.md`.
- **`[[wikilinks]]`**: at least **2 per note**. Links turn loose notes into a graph — and
  feed graphify.
- **Write bilingual where it matters**: notes you want accessible in both languages can be
  kept DE+EN (recall finds them cross-language anyway).
- **Never delete without asking**: notes are not silently removed — `/lessons-gc` always
  asks.
- **In lessons**: a `## Fix` must be **verified**; failed attempts go under
  `## Was NICHT funktioniert` ("what did NOT work").

---

## 4. Notiztypen / Note types

### DE

| `kind` | Liegt in | Zweck |
|--------|----------|-------|
| `lesson` | `lessons/` | Ein Fehler + verifizierter Fix + Warum. Treibt den Recall-Hook. |
| `idea` | `ideas/{hooks,video,posting,product}/` | Eine Idee, frictionless festgehalten. |
| `knowledge` | `knowledge/{coding,design,marketing,business}/` | Kuratiertes Sachwissen pro Domäne. |
| `project-hub` | `projects/` | Übersichts-Note pro Projekt; verlinkt alles Zugehörige. |
| `decision` | i. d. R. beim Projekt | Eine getroffene Architektur-/Produktentscheidung + Begründung. |
| `profile` | `profile/` | Deine Standards/Vorlieben (Design, Stil, Ansprüche). |
| `log` | `logs/` | Datiertes Session-Log (von `/save`). |
| `permanent` | `permanent/` | Langlebige, kuratierte Evergreen-Note. |

### EN

| `kind` | Lives in | Purpose |
|--------|----------|---------|
| `lesson` | `lessons/` | One error + verified fix + why. Drives the recall hook. |
| `idea` | `ideas/{hooks,video,posting,product}/` | One idea, captured frictionlessly. |
| `knowledge` | `knowledge/{coding,design,marketing,business}/` | Curated subject knowledge per domain. |
| `project-hub` | `projects/` | Overview note per project; links everything related. |
| `decision` | usually with the project | One architecture/product decision made + its rationale. |
| `profile` | `profile/` | Your standards/preferences (design, style, bar). |
| `log` | `logs/` | Dated session log (from `/save`). |
| `permanent` | `permanent/` | Long-lived, curated evergreen note. |

---

## 5. Templates (`_templates/`)

### DE

Die Vorlagen in `_templates/` geben jedem Notiztyp eine konsistente Struktur (Frontmatter
+ Standard-Überschriften), damit du nicht bei null anfängst und Recall verlässlich greift:

| Template | Wofür |
|----------|-------|
| `lesson.md` | Lesson-Gerüst: Frontmatter + `## Problem`, `## Fix` (verifiziert), `## Warum`, `## Was NICHT funktioniert`. |
| `idea.md` | Idee: Frontmatter (`kind: idea`, passende Kategorie) + Einzeiler-Platz. |
| `knowledge.md` | Wissensnote: Frontmatter + Domäne + Inhalt + Wikilinks. |
| `project-hub.md` | Projekt-Hub: Status, offene Punkte, Links zu Lessons/Decisions/Logs. |
| `decision.md` | Entscheidungsnote: Kontext, Entscheidung, Begründung, Konsequenzen. |
| `log.md` | Session-Log-Gerüst für `/save` (datiert, mit Wikilinks). |

Hinweis: Jedes Template erfüllt die Vault-Regeln ab Zeile eins — Pflicht-Frontmatter,
kebab-case-fähiger Titel und Platz für ≥2 Wikilinks.

### EN

The templates in `_templates/` give each note type a consistent structure (frontmatter +
standard headings) so you never start from scratch and recall reliably catches the note:

| Template | For |
|----------|-----|
| `lesson.md` | Lesson scaffold: frontmatter + `## Problem`, `## Fix` (verified), `## Why`, `## What did NOT work`. |
| `idea.md` | Idea: frontmatter (`kind: idea`, matching category) + one-liner space. |
| `knowledge.md` | Knowledge note: frontmatter + domain + body + wikilinks. |
| `project-hub.md` | Project hub: status, open items, links to lessons/decisions/logs. |
| `decision.md` | Decision note: context, decision, rationale, consequences. |
| `log.md` | Session-log scaffold for `/save` (dated, with wikilinks). |

Note: every template satisfies the vault rules from line one — mandatory frontmatter, a
kebab-case-ready title, and room for ≥2 wikilinks.
