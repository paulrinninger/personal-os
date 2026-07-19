# Concepts / Mental Model

> **DE zuerst, dann EN.** Each section has a German half and an English half.

Personal OS ist ein dauerhaftes, projektübergreifendes Gedächtnis für Claude Code in
einfachem Markdown, das dir gehört — $0, vollständig lokal. Dieses Dokument erklärt das
mentale Modell dahinter.

Personal OS is a persistent, cross-project memory for Claude Code in plain markdown you
own — $0, fully local. This document explains the mental model behind it.

---

## 1. Die Kernschleife: Capture → Recall → Maintain

### DE

Alles dreht sich um eine Schleife mit drei Phasen:

- **Capture** — Erkenntnisse festhalten: Fehler+Fix+Warum (Lessons), Ideen, Wissen,
  Session-Logs. Niedrige Reibung per Slash-Command.
- **Recall** — das Festgehaltene zur richtigen Zeit zurückholen: automatisch bei jedem
  Prompt und genau vor riskanten Aktionen.
- **Maintain** — den Speicher scharf halten: kalte/veraltete/doppelte Lessons prüfen,
  Gesundheit messen.

```
        ┌─────────────────────────────────────────────────┐
        │                                                  │
        ▼                                                  │
   ┌─────────┐      ┌──────────┐      ┌──────────────┐     │
   │ CAPTURE │ ───▶ │  RECALL  │ ───▶ │  MAINTAIN    │ ────┘
   │ /lesson │      │ auto-    │      │ /lessons-gc  │
   │ /idea   │      │ inject   │      │ /os health   │
   │ /save   │      │ on every │      │ fire-log     │
   └─────────┘      │ prompt + │      │ measure loop │
        ▲           │ pre-tool │      └──────────────┘
        │           └──────────┘
        │                │
        └─── you write ──┘  Claude reads, at the moment it matters
```

### EN

Everything revolves around one three-phase loop:

- **Capture** — record what you learn: error+fix+why (lessons), ideas, knowledge, session
  logs. Low-friction via slash command.
- **Recall** — bring the captured thing back at the right moment: automatically on every
  prompt and right before risky actions.
- **Maintain** — keep the store sharp: review cold/stale/duplicate lessons, measure health.

```
        ┌─────────────────────────────────────────────────┐
        │                                                  │
        ▼                                                  │
   ┌─────────┐      ┌──────────┐      ┌──────────────┐     │
   │ CAPTURE │ ───▶ │  RECALL  │ ───▶ │  MAINTAIN    │ ────┘
   │ /lesson │      │ auto-    │      │ /lessons-gc  │
   │ /idea   │      │ inject   │      │ /os health   │
   │ /save   │      │ on every │      │ fire-log     │
   └─────────┘      │ prompt + │      │ measure loop │
        ▲           │ pre-tool │      └──────────────┘
        │           └──────────┘
        │                │
        └─── you write ──┘  Claude reads, at the moment it matters
```

---

## 2. Warum automatischer Recall passive Notizen schlägt

### DE

Eine Notizsammlung, die nur dann hilft, wenn du dich erinnerst, sie zu öffnen, hilft in
der Praxis selten. Genau im Moment, in dem du den gleichen Fehler ein zweites Mal machst,
denkst du nicht an die Notiz von vor drei Wochen.

Personal OS dreht das um: **das Wissen kommt zu dir**, nicht umgekehrt. Bei *jedem* Prompt
durchsucht ein Hook lokal und semantisch deine vergangenen Lessons und spielt passende
Treffer in Claudes Kontext ein — bevor Claude überhaupt antwortet. Dokumentierte Fehler
wiederholen sich dadurch nicht. Aus einem passiven Archiv wird ein aktiver Reflex.

### EN

A note collection that only helps when you remember to open it rarely helps in practice.
At the exact moment you're about to repeat a mistake, you're not thinking about the note
you wrote three weeks ago.

Personal OS flips this: **the knowledge comes to you**, not the other way around. On
*every* prompt, a hook runs a local semantic search over your past lessons and injects
matching hits into Claude's context — before Claude even answers. Documented mistakes
stop repeating. A passive archive becomes an active reflex.

---

## 3. Zwei Abruf-Modi: qmd vs. graphify

### DE

Das wichtigste mentale Modell des Systems. Merksatz: **„qmd = Bedeutung, graphify =
Struktur."** Beide sind $0 und lokal, beide ergänzen sich.

| | **qmd** | **graphify** |
|---|---------|--------------|
| Frage | „Kennen wir das? Was wissen wir über X?" | „Was hängt mit X zusammen? Was bricht, wenn ich es ändere?" |
| Modus | **Bedeutung** (semantisch) | **Struktur** (Wissensgraph) |
| Technik | Hybrid BM25 + Vektor + RRF + Reranker | Graph mit `query`/`path`/`explain`/`affected` |
| Mehrsprachig | ja (Qwen3-Embedding) | über Knoten-/Kantennamen |
| Liefert | zitierte Passagen + Score | verbundene Knoten, Pfade, Blast-Radius |
| Kosten | $0, lokal | $0, lokal |

Faustregel: Bedeutung/Passagen → qmd. Struktur/Verbindungen → graphify.

### EN

The system's most important mental model. Mantra: **"qmd = meaning, graphify =
structure."** Both are $0 and local, and they complement each other.

| | **qmd** | **graphify** |
|---|---------|--------------|
| Question | "Have we seen this? What do we know about X?" | "What's connected to X? What breaks if I change it?" |
| Mode | **meaning** (semantic) | **structure** (knowledge graph) |
| Technique | hybrid BM25 + vector + RRF + reranker | graph with `query`/`path`/`explain`/`affected` |
| Multilingual | yes (Qwen3-Embedding) | via node/edge names |
| Returns | cited passages + score | connected nodes, paths, blast radius |
| Cost | $0, local | $0, local |

Rule of thumb: meaning/passages → qmd. structure/connections → graphify.

---

## 4. Die $0/lokal-Philosophie

### DE

Personal OS setzt **nie** einen API-Key. Jede Inferenz läuft auf deiner Maschine: qmd über
lokale GGUF-Modelle, ollama lokal. **Keine Daten verlassen den Rechner.** Dein Gedächtnis
liegt als einfaches Markdown in einem Ordner, den du besitzt, versionierst und backupst —
keine Cloud, kein Abo, kein Vendor-Lock-in. Genau das macht es vertrauenswürdig genug, um
dein echtes Arbeitsgedächtnis zu sein.

### EN

Personal OS **never** sets an API key. All inference runs on your machine: qmd via local
GGUF models, ollama local. **No data leaves the machine.** Your memory lives as plain
markdown in a folder you own, version, and back up — no cloud, no subscription, no vendor
lock-in. That's exactly what makes it trustworthy enough to be your real working memory.

---

## 5. Wie die Recall-Schleife verdrahtet ist

### DE

Die Magie sind **zwei Hooks** plus ein Fire-Log:

- **`recall-lessons.py`** — ein `UserPromptSubmit`-Hook. Läuft bei *jedem* Prompt, macht
  eine lokale semantische Suche (`qmd vsearch`, kein API, $0) und injiziert passende
  vergangene Lessons in Claudes Kontext. So wiederholen sich dokumentierte Fehler nicht.
- **`risk-recall.py`** — ein `PreToolUse`-Hook. Feuert genau vor riskanten/nach-außen
  gerichteten Aktionen (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel,
  `npm publish`, DB drop/delete, Mailversand) und holt relevante Lessons im Moment der
  Aktion erneut hervor.

Beide sind **rein informativ und blockieren nie**. Sie teilen sich ein append-only
**Fire-Log** (`lesson-fires.jsonl`): jeder Treffer wird protokolliert. Dieses Log treibt
die Health-/Mess-Schleife an — du siehst, welche Lessons wirklich feuern und welche kalt
sind.

### EN

The magic is **two hooks** plus a fire-log:

- **`recall-lessons.py`** — a `UserPromptSubmit` hook. Runs on *every* prompt, does a local
  semantic search (`qmd vsearch`, no API, $0), and injects matching past lessons into
  Claude's context. That's how documented mistakes stop repeating.
- **`risk-recall.py`** — a `PreToolUse` hook. Fires right before risky/outward actions
  (`git push --force`, `rm -rf`, `reset --hard`, deploy/vercel, `npm publish`, db
  drop/delete, sending mail) and re-surfaces relevant lessons at the moment of action.

Both are **purely informational and never block**. They share an append-only **fire-log**
(`lesson-fires.jsonl`): every hit is recorded. That log powers the health/measure loop —
you can see which lessons actually fire and which have gone cold.

---

## 6. Mehrsprachiger Recall

### DE

Du schreibst Notizen in der Sprache, die im Moment am natürlichsten ist — Deutsch,
Englisch, gemischt. Der Recall funktioniert **über Sprachgrenzen hinweg**: qmds
semantische Suche nutzt mehrsprachige Embeddings (Qwen3-Embedding), sodass ein
englischer Prompt eine deutsche Lesson findet und umgekehrt. Du musst nicht raten, in
welcher Sprache du etwas damals notiert hast.

### EN

You write notes in whatever language is most natural at the time — German, English, mixed.
Recall works **across language boundaries**: qmd's semantic search uses multilingual
embeddings (Qwen3-Embedding), so an English prompt finds a German lesson and vice versa.
You never have to guess which language you wrote something down in.

---

## 7. Der Selbstheilungs-Layer: Auto-Harvest & Doctor / The self-heal layer: auto-harvest & doctor

### DE

Zwei Mechanismen erweitern die **Maintain**-Phase aus Abschnitt 1 zu „Self-Heal" — das System
schließt seine eigenen Lücken und überwacht seine eigene Gesundheit:

- **Auto-Harvest.** Eine Session, die echte Arbeit tut (Edit/Write/Bash) aber **ohne `/save`** endet,
  würde ihre Lessons verlieren. Der Stop-Hook erkennt das und legt eine Breadcrumb in eine
  Harvest-Queue. **`/harvest`** destilliert solche Sessions später — interaktiv, mit dir im Loop — in
  eine **Review-Inbox** (`_inbox/`, bewusst außerhalb der qmd-Collection, damit ungeprüfte Drafts den
  Recall nicht verfälschen). Du promotest per Y/N. So schließt sich die Capture-Lücke, ohne eine
  headless LLM-Pipeline und ohne Kosten ($0).
- **Self-Health-Doctor.** **`/os doctor`** (→ `os_doctor.py`) prüft deterministisch, ob die Maschinerie
  selbst lebt: feuern die Recall-Hooks, ist der qmd-Index frisch, ist die Harvest-Queue/Inbox
  abgearbeitet, verrotten Lessons. Er läuft auch nächtlich — das System beobachtet seine eigene
  Gesundheit, statt still zu verrotten.

Beides ist „Maintain", eine Stufe weitergedacht: nicht nur den Speicher pflegen, sondern den **Loop
selbst** am Leben halten.

### DE — Dreaming: die nächtliche Konsolidierung

Menschliche Gedächtnisse konsolidieren im Schlaf — Personal OS auch (Opt-in,
`--schedule-dream`). Einmal pro Nacht verdichtet eine lokale Engine den Tagesrest,
findet fehlende `[[Verbindungen]]` zwischen Notizen, erkennt Feuer-Muster im
Recall (inkl. der *Misses*), kaut Lesson-Merges vor, rankt die Review-Inbox gegen
deine aktiven Projekte, prüft neue Projekte gegen die „Form" vergangener gescheiterter
Ventures und rendert (aus einer Lead-Queue, die du selbst befüllst) Outreach-Entwürfe.
Die Pässe rechnen nur — die risikoarme Schicht ihrer Ergebnisse führt der
**Autopilot** aus (Sektion 8), der Rest landet als Hinweise im **Nachtjournal**
(`_inbox/dreams/`, gitignored). Versendet wird nie etwas automatisch. Feedback
entsteht implizit (Undo = rejected, Überleben = accepted) und verschiebt die
Schwellwerte des jeweiligen Passes (Zähler, kein ML). Nur der Tagesrest-Pass MUSS
ein LLM benutzen (klein, lokal, hart gedeckelt; ventures darf einen einzigen Call
fürs Verdikt machen); Kill-Switch: `dream.off` im State-Home. Dreaming ist die
Maintain-Phase, die von allein läuft — der Vault wird über Nacht *vernetzter*,
nicht nur größer.

### EN — Dreaming: overnight consolidation

Human memory consolidates during sleep — so does Personal OS (opt-in,
`--schedule-dream`). Once a night, a local engine condenses yesterday's residue,
finds missing `[[connections]]` between notes, spots firing patterns in recall
(including the *misses*), pre-chews lesson merges, ranks the review inbox against
your active projects, checks new projects against the "shape" of past failed
ventures, and renders outreach drafts (from a lead queue you fill yourself).
The passes only compute — the low-risk share of their output is executed by the
**autopilot** (section 8), the rest lands as hints in the **night journal**
(`_inbox/dreams/`, gitignored). Nothing is ever sent automatically. Feedback happens
implicitly (undo = rejected, survival = accepted) and nudges that pass's thresholds
(counters, not ML). Only the residue pass MUST use an LLM (small, local, hard-capped;
ventures may make a single call to phrase its verdict); kill switch: `dream.off` in
the state home. Dreaming is the Maintain phase that runs by itself — overnight the
vault gets *more connected*, not just bigger.

### EN

Two mechanisms extend the **Maintain** phase from section 1 into "self-heal" — the system closes its
own gaps and watches its own health:

- **Auto-harvest.** A session that does real work (Edit/Write/Bash) but ends **without `/save`** would
  lose its lessons. The Stop hook notices and drops a breadcrumb into a harvest queue. **`/harvest`**
  later distills such sessions — interactively, with you in the loop — into a **review inbox**
  (`_inbox/`, deliberately outside the qmd collection so un-reviewed drafts can't skew recall). You
  promote them with a Y/N. The capture gap closes without a headless LLM pipeline and at no cost ($0).
- **Self-health doctor.** **`/os doctor`** (→ `os_doctor.py`) deterministically checks that the
  machinery itself is alive: are the recall hooks firing, is the qmd index fresh, is the harvest
  queue/inbox drained, are lessons rotting. It also runs nightly — the system watches its own health
  instead of quietly rotting.

Both are "Maintain" taken one step further: not just keeping the store tidy, but keeping the **loop
itself** alive.

---

## 8. Der stille Autopilot & die Vertrauens-Inversion / The silent autopilot & the trust inversion

### DE

Die erste Dreaming-Version fragte höflich: jede Nacht eine Vorschlagsnotiz, jede
Checkbox wartete auf Review. Das Ergebnis war messbar — die Notizen stapelten sich,
reviewt wurde keine. Die ehrliche Konsequenz: **Vorab-Genehmigung, die nie stattfindet,
ist keine Sicherheit.** Also invertiert der Autopilot den Vertrag für die risikofreie
Schicht: still ausführen, alles journalen, Undo billiger machen als Genehmigung.

Die drei Bausteine:

- **Das Journal ist das Fundament** (`actions.jsonl`): keine Aktion ohne verbatim
  Undo-Daten, geschrieben *bevor* du sie je siehst. `/undo` rollt eine Nacht in unter
  einer Minute zurück — mit Precondition-Checks: was du inzwischen selbst geändert
  hast, wird übersprungen, nie überschrieben. Sicherheit = Post-hoc-Undo statt
  Vorab-Genehmigung.
- **Feedback ohne Ritual**: jedes Undo zählt als *rejected*; ein nächtlicher Scanner
  bewertet, was du mit den Artefakten stillschweigend getan hast (Link zwei Wochen
  behalten = accepted, Draft promotet = accepted, 45 Tage unberührt = rejected). Die
  adaptiven Schwellwerte bekommen mehr Signal als das Review-Ritual je geliefert hat.
- **Die riskante Richtung ist bewacht** (`guard.py`): deine meistfeuernden Lessons
  werden zu deterministischen deny/ask/warn-Regeln kompiliert — benannte Probes im
  Code, nie Shell aus JSON, fail-open bei jedem Fehler, `POS_GUARD=skip` als geloggte
  Notluke, `ask-only` als Schattenwochen-Modus. Still handeln dürfen und riskantes
  Handeln abfangen sind zwei Seiten desselben Vertrags.

Tier-Grenzen bleiben hart: löschen nie, kuratierte Note-Bodies nie (außer dem
`## Links`-Append), `chats/`-Rohdateien und `profile/` nie, eigene Drafts promoten
nie. Kill-Switches gestaffelt: `autopilot.off` (nur Ausführung) · `dream.off` (alles).

### EN

The first dreaming version asked politely: one suggestions note per night, every
checkbox waiting for review. The result was measurable — the notes piled up, none got
reviewed. The honest conclusion: **up-front approval that never happens is not
safety.** So the autopilot inverts the contract for the risk-free tier: execute
silently, journal everything, make undo cheaper than approval.

The three building blocks:

- **The journal is the foundation** (`actions.jsonl`): no action without verbatim
  undo data, written *before* you ever see it. `/undo` rolls a night back in under a
  minute — with precondition checks: whatever you changed yourself in the meantime is
  skipped, never clobbered. Safety = post-hoc undo instead of up-front approval.
- **Feedback without a ritual**: every undo counts as *rejected*; a nightly scanner
  scores what you silently did with the artifacts (link kept two weeks = accepted,
  draft promoted = accepted, untouched for 45 days = rejected). The adaptive
  thresholds get more signal than the review ritual ever produced.
- **The risky direction is guarded** (`guard.py`): your top-firing lessons are
  compiled into deterministic deny/ask/warn rules — named probes in code, never shell
  from JSON, fail-open on any error, `POS_GUARD=skip` as the logged escape hatch,
  `ask-only` as the shadow-week mode. Being allowed to act silently and intercepting
  risky actions are two sides of the same contract.

Tier boundaries stay hard: never delete, never edit a curated note body (beyond the
`## Links` append), never touch `chats/` raw files or `profile/`, never promote its
own drafts. Kill switches are layered: `autopilot.off` (execution only) · `dream.off`
(everything).
