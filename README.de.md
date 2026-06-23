[English](README.md) · [Deutsch](README.de.md)

# Personal OS

> Gib Claude Code ein Gedächtnis, das es nicht verlieren kann — und das sich nicht wiederholt. Ein $0, local-first Wissenssystem in reinem Markdown, das dir gehört.

---

## Der 15-Sekunden-Pitch

Claude Code startet jede Sitzung mit Amnesie. Es fragt erneut, was du schon beantwortet hast, macht erneut Fehler, die du längst debuggt hast, und vergisst die mühsam getroffenen Entscheidungen der gestrigen Sitzung. Das Kontextfenster wird zurückgesetzt und dein hart erarbeitetes Wissen verdampft.

Die übliche Lösung ist ein „zweites Gehirn" — aber das ist **passiver Speicher**. Es hilft nur, wenn *du* daran denkst, es abzufragen — genau in dem Moment, in dem du vergessen hast, dass die Lektion überhaupt existiert. Ein Notizbuch, das du erst aufschlagen musst, ist kein Gedächtnis; es ist ein Aktenschrank.

**Personal OS ist anders: Es durchsucht sich selbst.** Bei *jedem* Prompt, den du absendest, läuft eine lokale semantische Suche und injiziert relevante frühere Lektionen direkt in Claudes Kontext — ohne Nachfrage. Direkt vor einer riskanten Aktion (ein Force-Push, ein `rm -rf`, ein Deploy) bringt es genau die Lektionen wieder an die Oberfläche, die in diesem Moment zählen. Alles läuft auf deiner Maschine, in reinem Markdown, das dir gehört, **ohne API-Keys und ohne Cloud — $0.**

---

## So funktioniert's

```
        ┌──────────────────────────────────────────────────────────┐
        │                                                          │
        │   CAPTURE (Erfassen)                                     │
        │   /save · /lesson · /idea                                │
        │         │                                                │
        │         ▼                                                │
        │   ┌───────────────────────────────┐                      │
        │   │   ~/vault  (Markdown, dein)   │                      │
        │   │   + lokaler semantischer Index│  ◄──── qmd / graphify│
        │   └───────────────────────────────┘                      │
        │         │                                                │
        │         ▼                                                │
        │   RECALL (Abruf — automatisch, zwei Hooks)               │
        │   recall-lessons.py  → bei jedem Prompt                  │
        │   risk-recall.py     → vor riskanten Aktionen            │
        │         │                                                │
        │         ▼                                                │
        │   MAINTAIN (Pflege)                                      │
        │   /os · /lessons-gc · /mine-chats · /resume             │
        │         │                                                │
        └─────────┘  ── neue Lektionen fließen zurück in Capture ──►
```

*Der Kreislauf: Du **erfasst** Wissen als reines Markdown, es wird lokal indexiert und **automatisch abgerufen** — bei jedem Prompt und erneut vor riskanten Aktionen in Claudes Kontext injiziert. **Pflege-**Befehle halten den Speicher scharf, und jede neue Lektion fließt zurück in den Kreislauf.*

---

## Die Magie: automatischer Abruf

Die meisten „Second Brain"-Tools sind passiver Speicher, den du abfragen musst. Personal OS durchsucht sich selbst. Zwei Hooks erledigen die Arbeit:

**`recall-lessons.py` — `UserPromptSubmit`**
Führt bei **jedem Prompt** eine **lokale semantische Suche** aus (`qmd vsearch`, $0, keine API) und injiziert die relevanten früheren Lektionen in Claudes Kontext. Das Ergebnis: Claude hört auf, dokumentierte Fehler zu wiederholen — *ohne dass du fragst*.

![Recall-Hook in Aktion](docs/media/recall-hook.svg)

<sub>Illustratives Standbild des echten injizierten Kontexts. Animierte Aufnahme erzeugen mit [`docs/media/recall-hook.tape`](docs/media/recall-hook.tape) (vhs).</sub>

**`risk-recall.py` — `PreToolUse`**
Feuert direkt **vor riskanten oder nach außen gerichteten Aktionen** — `git push --force`, `rm -rf`, `reset --hard`, Deploys, `npm publish`, Datenbank löschen, Mail senden — und bringt genau die Lektionen wieder an die Oberfläche, die in diesem Moment zählen, wenn ein Fehler tatsächlich teuer würde.

![Risk-Hook in Aktion](docs/media/risk-hook.svg)

<sub>Illustratives Standbild des echten injizierten Kontexts. Animierte Aufnahme erzeugen mit [`docs/media/risk-hook.tape`](docs/media/risk-hook.tape) (vhs).</sub>

---

## Zwei Abruf-Modi: Bedeutung vs. Struktur

Personal OS bietet zwei komplementäre Wege des Abrufs — und ein einfaches mentales Modell, wann du welchen greifst.

| | **qmd** | **graphify** |
|---|---|---|
| **Beantwortet** | „Haben wir das schon gesehen?" | „Was hängt zusammen / was bricht?" |
| **Modus** | BEDEUTUNG (semantisch) | STRUKTUR (Wissensgraph) |
| **Wie** | Hybrid BM25 + Vektor + RRF + Rerank; multilingual | `query` / `path` / `explain` / `affected` |
| **Wofür** | Paraphrasierte oder cross-linguale Lektionen finden | Links und Blast-Radius über Notizen verfolgen |
| **Kosten** | $0, lokal | $0, lokal |

**Faustregel: qmd = Bedeutung, graphify = Struktur.** Beide sind $0 und laufen vollständig auf deiner Maschine.

---

## Quickstart

**Voraussetzungen:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) und Python 3.

```bash
# 1. Abruf-Abhängigkeiten installieren (jeweils unter eigener Lizenz — siehe Credits)
npm install -g @tobilu/qmd
uv tool install graphifyy

# 2. Personal OS klonen und installieren
git clone <repo> && cd personal-os
./install/install.sh
```

Der Installer:

- legt `~/vault` an (dein Markdown-Gedächtnis),
- führt die Commands, Hooks und Skills in `~/.claude` zusammen — **ohne** deine bestehenden Settings zu überschreiben,
- schreibt die qmd-Index-Konfiguration und
- baut den ersten Index.

Dann öffne Claude Code in **irgendeinem** Projekt und probiere `/lesson`, `/save`, `/os`.

---

## Befehle

| Befehl | Was er tut |
|---|---|
| `/save` | Schreibt ein datiertes Session-Log; erntet automatisch Lektionen & Ideen aus der Sitzung |
| `/resume` | Kontext rekonstruieren — neueste Session-Logs und Entscheidungen lesen, Stand zusammenfassen |
| `/lesson` | Erfasst einen Fehler + Fix + *Warum* (dedupliziert gegen bestehende Lektionen) |
| `/idea` | Erfasst eine Idee (`hook` \| `video` \| `posting` \| `product`) |
| `/os` | Dashboard über alle Projekte — Lektionen, Ideen, Hubs, offene Punkte |
| `/mine-chats` | Destilliert Learnings aus importierten Chat-Transkripten |
| `/lessons-gc` | Prunt kalte, veraltete und doppelte Lektionen, um den Speicher scharf zu halten |

---

## Anforderungen

- **OS:** macOS oder Linux (Windows via WSL)
- **Claude Code** und **Python 3**
- **qmd** — erforderlich (semantischer Abruf)
- **graphify** — optional (struktureller Abruf)
- **ollama** — optional (nur für den Dedup-Durchlauf in `/lessons-gc`)

Das Repo wird **datenfrei** ausgeliefert: nur das Framework plus eine Handvoll generischer Beispiel-Notizen (z. B. *„never force-push a shared branch"*, *„cap LLM API costs"*). Siehe [`docs/`](docs/) für **SETUP**, **CONCEPTS**, **VAULT** und **COMMANDS** sowie [`docs/examples/os-dashboard.md`](docs/examples/os-dashboard.md) für ein Beispiel-Dashboard.

---

## Kosten & Privatsphäre

**$0. Lokal. Dein.** Personal OS verwendet niemals einen API-Key. Sämtliche Inferenz läuft auf deiner eigenen Maschine, und **deine Daten verlassen niemals deinen Laptop.** Es funktioniert über **alle** deine Projekte hinweg, nicht nur ein Repo. Der Vault ist reines Markdown, das dir gehört — keine Datenbank, keine Cloud, kein Lock-in.

---

## FAQ

**Brauche ich API-Keys?**
Nein. Niemals. Der gesamte Abruf läuft lokal über `qmd vsearch`. Es gibt keinen Kostenpfad.

**Funktioniert es unter Windows?**
Ja, via WSL. Native Ziele sind macOS und Linux.

**Kann ich meinen bestehenden Obsidian-Vault nutzen?**
Ja — der Vault ist einfach ein Obsidian-artiger Markdown-Ordner. Der Installer legt `~/vault` an und überschreibt keine bestehenden `~/.claude`-Settings; richte den Index auf deinen eigenen Vault, wenn du magst.

**Was, wenn ich graphify / ollama weglasse?**
Beide sind optional. Ohne graphify verlierst du den strukturellen (Graph-)Abruf, behältst aber den vollen semantischen Abruf. Ohne ollama verlierst du nur den Dedup-Durchlauf in `/lessons-gc`. qmd ist die einzige erforderliche Abhängigkeit.

**Werden meine Daten irgendwohin gesendet?**
Nein. Die Inferenz ist lokal und der Vault bleibt auf deiner Maschine. Es wird nichts hochgeladen.

**Ist es zweisprachig?**
Ja. Der semantische Abruf nutzt multilinguale Qwen3-Embeddings, sodass deine Notizen in jeder Sprache sein können und der Abruf *sprachübergreifend* funktioniert — eine auf Deutsch geschriebene Lektion taucht bei einem englischen Prompt auf, und umgekehrt.

---

## Credits & Attribution

Personal OS steht auf zwei exzellenten lokalen Tools:

- **qmd** — semantische Suche. Von Tobi Lutke. MIT. https://github.com/tobi/qmd
- **graphify** — Wissensgraph. Von Safi Shamsi. MIT. https://github.com/safishamsi/graphify
- **ollama** — optionale lokale Inferenz für den `/lessons-gc`-Dedup. https://ollama.com

> **qmd und graphify sind erforderlich, werden aber NICHT mitgeliefert (vendored) — du installierst sie selbst; dieses Repo liefert ihren Code niemals aus.** Jedes bleibt unter seiner eigenen Lizenz.

---

## Lizenz

MIT. Siehe [`LICENSE`](LICENSE).
