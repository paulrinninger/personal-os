[English](README.md) · [Deutsch](README.de.md)

# Personal OS

> **Gib Claude Code ein Gedächtnis, das es nicht verlieren kann — und das sich nicht wiederholt.**
> Ein lokales Wissenssystem für $0, in reinem Markdown, das dir gehört, und das bei jedem Prompt *automatisch* die passende Lesson abruft.

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Cost: $0](https://img.shields.io/badge/cost-%240-brightgreen)
![Inference: 100% local](https://img.shields.io/badge/inference-100%25%20local-success)
![API keys: none](https://img.shields.io/badge/API%20keys-none-informational)
![For: Claude Code](https://img.shields.io/badge/for-Claude%20Code-8A2BE2)

---

## Der Pitch in 15 Sekunden

Claude Code startet jede Session mit Amnesie. Es stellt Fragen erneut, die du längst beantwortet hast, macht Fehler wieder, die du schon debuggt hast, und vergisst die hart erkämpften Entscheidungen von gestern. Das Kontextfenster setzt sich zurück und dein Wissen verdampft.

Die übliche Lösung ist ein „zweites Gehirn“ — aber das ist **passiver Speicher**. Es hilft nur, wenn *du* daran denkst, es abzufragen — also genau in dem Moment, in dem du längst vergessen hast, dass die Lesson überhaupt existiert. Ein Notizbuch, das du erst aufschlagen musst, ist kein Gedächtnis; es ist ein Aktenschrank.

**Personal OS ist anders: Das Gedächtnis durchsucht sich selbst.** Bei *jedem* Prompt läuft eine lokale semantische Suche und schiebt die relevanten vergangenen Lessons direkt in Claudes Kontext — ungefragt. Direkt vor einer riskanten Aktion (ein Force-Push, ein `rm -rf`, ein Deploy) holt es genau die Lessons wieder hoch, die *in diesem exakten Moment* zählen. Alles läuft auf deiner Maschine, in reinem Markdown, das dir gehört, **ohne API-Keys und ohne Cloud — $0.**

---

## Warum das eine große Sache ist

Was KI-Coding ausbremst, ist nicht Intelligenz — es ist **Amnesie**. Personal OS behebt das eine fehlende Teil, und zwar so, dass es auf jeder Achse zugleich kaum zu schlagen ist:

- 🧠 **Recall ist automatisch, nicht manuell.** Speichern ist leicht; *im richtigen Moment ans Abrufen zu denken* ist der schwere Teil. Zwei Hooks machen das Abrufen unwillkürlich — bei jedem Prompt, und noch einmal direkt vor allem Riskanten.
- 📈 **Es verzinst sich.** Jede Lesson, die du festhältst, zahlt sich für immer weiter aus, weil sie bei jedem künftigen Prompt in jedem Projekt kostenlos abgerufen wird. Wissen wächst an, statt sich zurückzusetzen.
- ✂️ **Es bleibt scharf.** Anders als ein Notizenhaufen, der nur wächst, *misst* es, welche Lessons tatsächlich feuern, und *prunet* den toten Ballast — so steigt die Recall-Qualität mit der Zeit, statt zu sinken.
- 🔒 **Es gehört dir, und es ist kostenlos.** Reines Markdown auf deiner Platte, keine Datenbank, kein Anbieter, kein Lock-in. Sämtliche Inferenz läuft über lokale GGUF-Modelle — **niemals ein API-Key, $0** — also verlassen dein Code und deine Notizen nie die Maschine.
- 🌍 **Es ist sprachunabhängig.** Recall ist semantisch und mehrsprachig: Eine auf Deutsch geschriebene Lesson taucht bei einem englischen Prompt auf, und umgekehrt.

---

## Das Schwungrad

Die meisten Notizsysteme füllen sich nur. Personal OS dreht eine geschlossene Schleife, die das Gedächtnis **schärfer macht, je mehr du es nutzt**:

![Das Personal-OS-Schwungrad](docs/media/flywheel.svg)

Festhalten → indexieren → **Recall (automatisch)** → anwenden → **messen**, was tatsächlich gefeuert hat → **prunen**, was es nie tut. Eine Lesson verdient ihren Platz nur, wenn sie feuert; nie gefeuerte Lessons werden archiviert, häufig gefeuerte geschärft. Genau dieser Schritt aus Messen und Prunen hält den Recall präzise, statt in Beinahe-Duplikaten zu ertrinken.

---

## Wie es gebaut ist

Drei dünne Schichten, alle auf deiner Maschine — das Festhalten fließt nach unten, der Recall wieder nach oben:

![Architektur: drei lokale Schichten](docs/media/architecture.svg)

1. **Dein Vault** — ein Obsidian-artiger Ordner aus reinem Markdown (`lessons/`, `ideas/`, `knowledge/`, `projects/`, `logs/`, `profile/`). Dir gehört jede Datei.
2. **Claude-Code-Integration** — zwei Hooks (`recall-lessons.py`, `risk-recall.py`), sieben Slash-Befehle und eine kleine Mess-/Prune-Engine, eingebunden in `~/.claude`, ohne dein bestehendes Setup anzurühren.
3. **Lokale Engines** — [`qmd`](https://github.com/tobi/qmd) für semantische Suche, [`graphify`](https://github.com/safishamsi/graphify) für Graph-Abfragen, optional `ollama` für Dedup. Alles $0, alles offline.

Das Ganze installiert sich mit einem einzigen Befehl und ist vollständig reversibel.

---

## Der Clou: zweistufiger automatischer Recall

Zwei Hooks erledigen die Arbeit — und genau das gibt dir keine passive Notiz-App:

**`recall-lessons.py` — `UserPromptSubmit`** führt bei **jedem Prompt** eine **lokale semantische Suche** aus (`qmd vsearch`, $0, keine API) und injiziert die relevanten vergangenen Lessons in Claudes Kontext. Claude hört auf, dokumentierte Fehler zu wiederholen — *ohne dass du fragst*.

![Recall-Hook feuert](docs/media/recall-hook.svg)

<sub>Illustratives Standbild des real injizierten Kontexts. Erzeuge eine animierte Aufnahme mit [`docs/media/recall-hook.tape`](docs/media/recall-hook.tape) (vhs).</sub>

**`risk-recall.py` — `PreToolUse`** feuert direkt **vor riskanten oder nach außen wirkenden Aktionen** — `git push --force`, `rm -rf`, `reset --hard`, Deploys, `npm publish`, eine Datenbank droppen, Mail verschicken — und holt genau die Lessons wieder hoch, die in dem präzisen Moment zählen, in dem ein Fehler dich teuer zu stehen käme.

![Risk-Hook feuert](docs/media/risk-hook.svg)

<sub>Illustratives Standbild des real injizierten Kontexts. Erzeuge eine animierte Aufnahme mit [`docs/media/risk-hook.tape`](docs/media/risk-hook.tape) (vhs).</sub>

---

## Worauf es sich mit der Zeit aufsummiert

Das ist der Teil, der ein Gedächtnis von einem Notizbuch trennt. Ein zustandsloser Assistent startet jede Session für immer bei null. Personal OS klettert immer weiter:

![Wachsender Wert über die Zeit](docs/media/compounding.svg)

- **Woche 1** — du hältst deine ersten Lessons fest; der Recall fängt an, sie hochzuspülen.
- **Monat 3** — der Recall feuert täglich; dieselben Fehler hören schlicht auf, wiederzukehren.
- **Monat 6** — projektübergreifende Muster tauchen von selbst auf; `/lessons-gc` hält den Speicher kompakt.
- **Monat 12** — es arbeitet wie ein erfahrener Teamkollege, der sich an *alles erinnert, was du je gelernt hast* — und es hat dich $0 gekostet und nie deinen Laptop verlassen.

---

## Wie es sich unterscheidet

| | Notiz-App / „zweites Gehirn“ | Cloud-KI-Assistent-Gedächtnis | **Personal OS** |
|---|:---:|:---:|:---:|
| Ruft **automatisch** ab, ohne Nachfrage | ✗ du musst suchen | ~ undurchsichtig, manchmal | ✓ jeder Prompt **+ vor riskanten Aktionen** |
| Ein Gedächtnis über **alle** Projekte | ~ passiv | ~ pro Produkt | ✓ jedes Repo |
| **Dir gehören** die Daten (reine Dateien) | ✓ | ✗ beim Anbieter | ✓ reines Markdown, lokal |
| Wird mit der Zeit **schärfer** | ✗ wächst nur | ✗ undurchsichtig | ✓ messen + prunen |
| Läuft **offline**, kein API-Key | ✓ | ✗ | ✓ 100 % lokal |
| **Kosten** | $ | $ / Abo | **$0** |

---

## Zwei Abrufmodi: Bedeutung vs. Struktur

| | **qmd** | **graphify** |
|---|---|---|
| **Beantwortet** | „Hatten wir das schon mal?“ | „Was hängt zusammen / was bricht?“ |
| **Modus** | BEDEUTUNG (semantisch) | STRUKTUR (Wissensgraph) |
| **Wie** | Hybrid aus BM25 + Vektor + RRF + Rerank; multilingual | `query` / `path` / `explain` / `affected` |
| **Wofür** | Paraphrasierte oder sprachübergreifende Lessons | Links und Blast-Radius über Notizen hinweg verfolgen |
| **Kosten** | $0, lokal | $0, lokal |

**Faustregel: qmd = meaning, graphify = structure.** Beide laufen vollständig auf deiner Maschine.

---

## Quickstart

**Voraussetzungen:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) und Python 3.

```bash
# 1. Install the retrieval dependencies (each under its own license — see Credits)
npm install -g @tobilu/qmd
uv tool install graphifyy

# 2. Clone and install Personal OS
git clone <repo> && cd personal-os
./install/install.sh
```

Der Installer legt `~/vault` an, führt die Befehle/Hooks/Skills in `~/.claude` zusammen — **ohne deine bestehenden Einstellungen zu überschreiben** —, schreibt die qmd-Index-Konfiguration und baut den ersten Index. Öffne dann Claude Code in **irgendeinem** Projekt und probiere `/lesson`, `/save`, `/os`. Prüfe die Verdrahtung jederzeit mit `python3 install/doctor.py` (es führt eine echte Recall-Abfrage Ende-zu-Ende aus).

---

## Befehle

| Befehl | Was er tut |
|---|---|
| `/save` | Schreibt ein datiertes Session-Log; erntet automatisch Lessons & Ideen aus der Session |
| `/resume` | Baut den Kontext neu auf — liest die neuesten Logs und Entscheidungen, fasst den Stand zusammen |
| `/lesson` | Hält einen Fehler + Fix + *Warum* fest (dedupliziert gegen bestehende Lessons) |
| `/idea` | Hält eine Idee fest (`hook` \| `video` \| `posting` \| `product`) |
| `/os` | Dashboard über alle Projekte — Lessons, Ideen, Hubs, offene Punkte |
| `/mine-chats` | Destilliert Learnings aus importierten Chat-Transkripten |
| `/lessons-gc` | Prunet kalte, veraltete und doppelte Lessons, um den Speicher scharf zu halten |

---

## Anforderungen

- **OS:** macOS oder Linux (Windows über WSL) · **Claude Code** · **Python 3**
- **qmd** — erforderlich (semantischer Recall) · **graphify** — optional (struktureller Recall) · **ollama** — optional (`/lessons-gc`-Dedup)

Das Repo wird **datenfrei** ausgeliefert: nur das Framework plus eine Handvoll generischer Beispiel-Notizen (z. B. *„never force-push a shared branch“*, *„cap LLM API costs“*). Siehe [`docs/`](docs/) für **SETUP**, **CONCEPTS**, **VAULT**, **COMMANDS** und [`docs/examples/os-dashboard.md`](docs/examples/os-dashboard.md) für ein Beispiel-Dashboard.

---

## Kosten & Datenschutz

**$0. Lokal. Deins.** Personal OS nutzt nie einen API-Key. Sämtliche Inferenz läuft auf deiner eigenen Maschine und **deine Daten verlassen nie deinen Laptop.** Es funktioniert über **alle** deine Projekte hinweg, nicht nur ein Repo. Der Vault ist reines Markdown, das dir gehört — keine Datenbank, keine Cloud, kein Lock-in.

---

## FAQ

**Brauche ich API-Keys?** Nein. Niemals. Sämtlicher Recall läuft lokal über `qmd vsearch`. Es gibt keinen Kostenpfad.

**Funktioniert es unter Windows?** Ja, über WSL. Native Ziele sind macOS und Linux.

**Kann ich meinen bestehenden Obsidian-Vault nutzen?** Ja — der Vault ist einfach ein Obsidian-artiger Markdown-Ordner. Der Installer überschreibt keine bestehenden `~/.claude`-Einstellungen; richte den Index auf deinen eigenen Vault, wenn du magst.

**Was, wenn ich graphify / ollama weglasse?** Beide sind optional. Ohne graphify verlierst du den strukturellen (Graph-)Recall, behältst aber den vollen semantischen Recall. Ohne ollama verlierst du nur den Dedup-Durchlauf in `/lessons-gc`. qmd ist die eine erforderliche Abhängigkeit.

**Werden meine Daten irgendwohin gesendet?** Nein. Die Inferenz ist lokal und der Vault bleibt auf deiner Maschine. Es wird nichts hochgeladen.

**Ist es zweisprachig?** Ja. Der semantische Recall nutzt multilinguale Qwen3-Embeddings, sodass deine Notizen in jeder Sprache sein können und der Recall *sprachübergreifend* funktioniert.

---

## Credits & Attribution

Personal OS steht auf zwei exzellenten lokalen Tools:

- **qmd** — semantische Suche. Von Tobi Lutke. MIT. https://github.com/tobi/qmd
- **graphify** — Wissensgraph. Von Safi Shamsi. MIT. https://github.com/safishamsi/graphify
- **ollama** — optionale lokale Inferenz für den `/lessons-gc`-Dedup. https://ollama.com

> **qmd und graphify sind erforderlich, werden aber NICHT mitgeliefert — du installierst sie selbst; dieses Repo liefert ihren Code nie aus.** Jedes bleibt unter seiner eigenen Lizenz.

---

## Lizenz

MIT. Siehe [`LICENSE`](LICENSE).
