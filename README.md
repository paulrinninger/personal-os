[English](README.md) · [Deutsch](README.de.md)

# Personal OS

> Give Claude Code a memory it can't lose — and won't repeat. A $0, local-first knowledge system in plain markdown you own.

---

## The 15-second pitch

Claude Code starts every session with amnesia. It re-asks questions you've answered, re-makes mistakes you've already debugged, and forgets the hard-won decisions from yesterday's session. The context window resets and your hard-earned knowledge evaporates.

The usual fix is a "second brain" — but those are **passive storage**. They only help if *you* remember to go query them, which is exactly the moment you've forgotten the lesson exists. A notebook you have to remember to open isn't a memory; it's a filing cabinet.

**Personal OS is different: it searches itself.** On *every* prompt you send, a local semantic search runs and injects relevant past lessons straight into Claude's context — no asking required. Right before a risky action (a force-push, an `rm -rf`, a deploy), it re-surfaces the lessons that matter at that exact moment. It all runs on your machine, in plain markdown you own, with **no API keys and no cloud — $0.**

---

## How it works

```
        ┌──────────────────────────────────────────────────────────┐
        │                                                          │
        │   CAPTURE                                                │
        │   /save · /lesson · /idea                                │
        │         │                                                │
        │         ▼                                                │
        │   ┌───────────────────────────────┐                      │
        │   │   ~/vault  (markdown you own) │                      │
        │   │   + local semantic index      │  ◄──── qmd / graphify│
        │   └───────────────────────────────┘                      │
        │         │                                                │
        │         ▼                                                │
        │   RECALL  (automatic — two hooks)                        │
        │   recall-lessons.py  → on every prompt                   │
        │   risk-recall.py     → before risky actions              │
        │         │                                                │
        │         ▼                                                │
        │   MAINTAIN                                               │
        │   /os · /lessons-gc · /mine-chats · /resume             │
        │         │                                                │
        └─────────┘  ──── new lessons feed back into Capture ──────►
```

*The loop: you **capture** knowledge as plain markdown, it's indexed locally, and it's **recalled** automatically — injected into Claude's context on every prompt and again before risky actions. **Maintenance** commands keep the store sharp, and every new lesson feeds back into the loop.*

---

## The magic: automatic recall

Most "second brain" tools are passive storage you must remember to query. Personal OS searches itself. Two hooks do the work:

**`recall-lessons.py` — `UserPromptSubmit`**
Runs a **local semantic search** (`qmd vsearch`, $0, no API) on **every prompt** and injects the relevant past lessons into Claude's context. The result: Claude stops repeating documented mistakes *without you asking*.

![Recall hook firing](docs/media/recall-hook.svg)

<sub>Illustrative still of the real injected context. Generate an animated capture with [`docs/media/recall-hook.tape`](docs/media/recall-hook.tape) (vhs).</sub>

**`risk-recall.py` — `PreToolUse`**
Fires right **before risky or outward actions** — `git push --force`, `rm -rf`, `reset --hard`, deploys, `npm publish`, dropping a database, sending mail — and re-surfaces the lessons that matter at that exact moment, when a mistake would actually cost you.

![Risk hook firing](docs/media/risk-hook.svg)

<sub>Illustrative still of the real injected context. Generate an animated capture with [`docs/media/risk-hook.tape`](docs/media/risk-hook.tape) (vhs).</sub>

---

## Two retrieval modes: meaning vs. structure

Personal OS gives you two complementary ways to recall, and a simple mental model for which to reach for.

| | **qmd** | **graphify** |
|---|---|---|
| **Answers** | "Have we seen this before?" | "What's connected / what breaks?" |
| **Mode** | MEANING (semantic) | STRUCTURE (knowledge graph) |
| **How** | Hybrid BM25 + vector + RRF + rerank; multilingual | `query` / `path` / `explain` / `affected` |
| **Use it for** | Finding paraphrased or cross-language lessons | Tracing links and blast radius across notes |
| **Cost** | $0, local | $0, local |

**Rule of thumb: qmd = meaning, graphify = structure.** Both are $0 and run entirely on your machine.

---

## Quickstart

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and Python 3.

```bash
# 1. Install the retrieval dependencies (each under its own license — see Credits)
npm install -g @tobilu/qmd
uv tool install graphifyy

# 2. Clone and install Personal OS
git clone <repo> && cd personal-os
./install/install.sh
```

The installer:

- creates `~/vault` (your markdown memory),
- merges the commands, hooks, and skills into `~/.claude` **without clobbering** your existing settings,
- writes the qmd index config, and
- builds the first index.

Then open Claude Code in **any** project and try `/lesson`, `/save`, `/os`.

---

## Commands

| Command | What it does |
|---|---|
| `/save` | Write a dated session log; auto-harvests lessons & ideas from the session |
| `/resume` | Rebuild context — read the newest session logs and decisions, summarize state |
| `/lesson` | Capture an error + fix + *why* (dedupes against existing lessons) |
| `/idea` | Capture an idea (`hook` \| `video` \| `posting` \| `product`) |
| `/os` | Dashboard across all projects — lessons, ideas, hubs, open points |
| `/mine-chats` | Distill learnings from imported chat transcripts |
| `/lessons-gc` | Prune cold, stale, and duplicate lessons to keep the store sharp |

---

## Requirements

- **OS:** macOS or Linux (Windows via WSL)
- **Claude Code** and **Python 3**
- **qmd** — required (semantic recall)
- **graphify** — optional (structural recall)
- **ollama** — optional (only for the dedup pass in `/lessons-gc`)

The repo ships **data-free**: just the framework plus a handful of generic example notes (e.g. *"never force-push a shared branch"*, *"cap LLM API costs"*). See [`docs/`](docs/) for **SETUP**, **CONCEPTS**, **VAULT**, and **COMMANDS**, and [`docs/examples/os-dashboard.md`](docs/examples/os-dashboard.md) for a sample dashboard.

---

## Cost & privacy

**$0. Local. Yours.** Personal OS never uses an API key. All inference runs on your own machine, and **your data never leaves your laptop.** It works across **all** your projects, not just one repo. The vault is plain markdown you own — no database, no cloud, no lock-in.

---

## FAQ

**Do I need API keys?**
No. Never. All recall runs locally via `qmd vsearch`. There is no cost path.

**Does it work on Windows?**
Yes, via WSL. Native targets are macOS and Linux.

**Can I use my existing Obsidian vault?**
Yes — the vault is just an Obsidian-style markdown folder. The installer creates `~/vault` and won't clobber existing `~/.claude` settings; point the index at your own vault if you prefer.

**What if I skip graphify / ollama?**
Both are optional. Without graphify you lose structural (graph) recall but keep full semantic recall. Without ollama you lose only the dedup pass in `/lessons-gc`. qmd is the one required dependency.

**Is my data sent anywhere?**
No. Inference is local and the vault stays on your machine. Nothing is uploaded.

**Is it bilingual?**
Yes. The semantic recall uses multilingual Qwen3 embeddings, so your notes can be in any language and recall works *across* languages — a lesson written in German surfaces for an English prompt, and vice versa.

---

## Credits & attribution

Personal OS stands on two excellent local tools:

- **qmd** — semantic search. By Tobi Lutke. MIT. https://github.com/tobi/qmd
- **graphify** — knowledge graph. By Safi Shamsi. MIT. https://github.com/safishamsi/graphify
- **ollama** — optional local inference for `/lessons-gc` dedup. https://ollama.com

> **qmd and graphify are required but NOT vendored — you install them yourself; this repo never ships their code.** Each remains under its own license.

---

## License

MIT. See [`LICENSE`](LICENSE).
