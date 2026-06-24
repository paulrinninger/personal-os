[English](README.md) · [Deutsch](README.de.md)

# Personal OS

> **Give Claude Code a memory it can't lose — and won't repeat.**
> A $0, local-first knowledge system in plain markdown you own, that recalls the right lesson *automatically* on every prompt.

![License: MIT](https://img.shields.io/badge/license-MIT-blue)
![Cost: $0](https://img.shields.io/badge/cost-%240-brightgreen)
![Inference: 100% local](https://img.shields.io/badge/inference-100%25%20local-success)
![API keys: none](https://img.shields.io/badge/API%20keys-none-informational)
![For: Claude Code](https://img.shields.io/badge/for-Claude%20Code-8A2BE2)

---

## The 15-second pitch

Claude Code starts every session with amnesia. It re-asks questions you've answered, re-makes mistakes you've already debugged, and forgets yesterday's hard-won decisions. The context window resets and your knowledge evaporates.

The usual fix is a "second brain" — but those are **passive storage**. They only help if *you* remember to go query them, which is exactly the moment you've already forgotten the lesson exists. A notebook you have to remember to open isn't a memory; it's a filing cabinet.

**Personal OS is different: the memory searches itself.** On *every* prompt, a local semantic search runs and slips the relevant past lessons straight into Claude's context — no asking. Right before a risky action (a force-push, an `rm -rf`, a deploy) it re-surfaces the lessons that matter *at that exact moment*. Everything runs on your machine, in plain markdown you own, with **no API keys and no cloud — $0.**

---

## Why this is a big deal

The thing holding AI coding back isn't intelligence — it's **amnesia**. Personal OS fixes the one missing piece, and does it in a way that is genuinely hard to beat on every axis at once:

- 🧠 **Recall is automatic, not manual.** Storage is easy; *remembering to retrieve at the right moment* is the hard part. Two hooks make retrieval involuntary — on every prompt, and again right before anything risky.
- 📈 **It compounds.** Every lesson you capture keeps paying off, forever, because it's recalled for free on every future prompt across every project. Knowledge accrues instead of resetting.
- ✂️ **It stays sharp.** Unlike a notes pile that only grows, it *measures* which lessons actually fire and *prunes* the dead weight — so recall quality goes up over time, not down. It even self-harvests lessons from sessions that ended without `/save`, and self-checks its own health (`/os doctor`).
- 🔒 **It's yours, and it's free.** Plain markdown on your disk, no database, no vendor, no lock-in. All inference is local GGUF models — **no API key, ever, $0** — so your code and notes never leave the machine.
- 🌍 **It's language-agnostic.** Recall is semantic and multilingual: a lesson written in German surfaces for an English prompt, and vice versa.

---

## The flywheel

Most note systems only fill up. Personal OS runs a closed loop that makes the memory **sharper the more you use it**:

![The Personal OS flywheel](docs/media/flywheel.svg)

Capture → index → **recall (automatic)** → apply → **measure** what actually fired → **prune** what never does. A lesson earns its place only if it fires; never-fired lessons get archived, frequently-fired ones get sharpened. That measure-and-prune step is what keeps recall precise instead of drowning in near-duplicates.

---

## How it's built

Three thin layers, all on your machine — capture flows down, recall flows back up:

![Architecture: three local layers](docs/media/architecture.svg)

1. **Your vault** — an Obsidian-style folder of plain markdown (`lessons/`, `ideas/`, `knowledge/`, `projects/`, `logs/`, `profile/`). You own every file.
2. **Claude Code integration** — two hooks (`recall-lessons.py`, `risk-recall.py`), eight slash commands, and a small measure/prune engine, merged into `~/.claude` without touching your existing setup.
3. **Local engines** — [`qmd`](https://github.com/tobi/qmd) for semantic search, [`graphify`](https://github.com/safishamsi/graphify) for graph queries, optional `ollama` for dedup. All $0, all offline.

The whole thing installs with one command and is fully reversible.

---

## The magic: two-tier automatic recall

Two hooks do the work — and this is what no passive notes app gives you:

**`recall-lessons.py` — `UserPromptSubmit`** runs a **local semantic search** (`qmd vsearch`, $0, no API) on **every prompt** and injects the relevant past lessons into Claude's context. Claude stops repeating documented mistakes *without you asking*.

![Recall hook firing](docs/media/recall-hook.svg)

<sub>Illustrative still of the real injected context. Generate an animated capture with [`docs/media/recall-hook.tape`](docs/media/recall-hook.tape) (vhs).</sub>

**`risk-recall.py` — `PreToolUse`** fires right **before risky or outward actions** — `git push --force`, `rm -rf`, `reset --hard`, deploys, `npm publish`, dropping a database, sending mail — and re-surfaces the lessons that matter at the precise moment a mistake would cost you.

![Risk hook firing](docs/media/risk-hook.svg)

<sub>Illustrative still of the real injected context. Generate an animated capture with [`docs/media/risk-hook.tape`](docs/media/risk-hook.tape) (vhs).</sub>

---

## What it compounds into over time

This is the part that separates a memory from a notebook. A stateless assistant starts at zero every session forever. Personal OS keeps climbing:

![Compounding value over time](docs/media/compounding.svg)

- **Week 1** — you capture your first lessons; recall starts surfacing them.
- **Month 3** — recall fires daily; the same mistakes simply stop recurring.
- **Month 6** — cross-project patterns surface on their own; `/lessons-gc` keeps the store tight.
- **Month 12** — it works like a senior teammate who remembers *everything you've ever learned* — and it cost you $0 and never left your laptop.

---

## How it's different

| | Notes app / "second brain" | Cloud AI assistant memory | **Personal OS** |
|---|:---:|:---:|:---:|
| Recalls **automatically**, no asking | ✗ you must search | ~ opaque, sometimes | ✓ every prompt **+ before risky actions** |
| One memory across **all** projects | ~ passive | ~ per-product | ✓ every repo |
| **You own** the data (plain files) | ✓ | ✗ vendor-held | ✓ plain markdown, local |
| Gets **sharper** over time | ✗ only grows | ✗ opaque | ✓ measure + prune |
| Runs **offline**, no API key | ✓ | ✗ | ✓ 100% local |
| **Cost** | $ | $ / subscription | **$0** |

---

## Two retrieval modes: meaning vs. structure

| | **qmd** | **graphify** |
|---|---|---|
| **Answers** | "Have we seen this before?" | "What's connected / what breaks?" |
| **Mode** | MEANING (semantic) | STRUCTURE (knowledge graph) |
| **How** | Hybrid BM25 + vector + RRF + rerank; multilingual | `query` / `path` / `explain` / `affected` |
| **Use it for** | Paraphrased or cross-language lessons | Tracing links and blast radius across notes |
| **Cost** | $0, local | $0, local |

**Rule of thumb: qmd = meaning, graphify = structure.** Both run entirely on your machine.

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

The installer creates `~/vault`, merges the commands/hooks/skills into `~/.claude` **without clobbering** your existing settings, writes the qmd index config, and builds the first index. Then open Claude Code in **any** project and try `/lesson`, `/save`, `/os`. Verify wiring anytime with `python3 install/doctor.py` (it runs a real recall query end-to-end).

---

## Commands

| Command | What it does |
|---|---|
| `/save` | Write a dated session log; auto-harvest lessons & ideas from the session |
| `/resume` | Rebuild context — read the newest logs and decisions, summarize state |
| `/lesson` | Capture an error + fix + *why* (dedupes against existing lessons) |
| `/idea` | Capture an idea (`hook` \| `video` \| `posting` \| `product`) |
| `/os` | Dashboard across all projects — lessons, ideas, hubs, open points |
| `/mine-chats` | Distill learnings from imported chat transcripts |
| `/lessons-gc` | Prune cold, stale, and duplicate lessons to keep the store sharp |
| `/harvest` | Distill lessons & ideas from sessions that ended without `/save`, into a review inbox |

---

## Requirements

- **OS:** macOS or Linux (Windows via WSL) · **Claude Code** · **Python 3**
- **qmd** — required (semantic recall) · **graphify** — optional (structural recall) · **ollama** — optional (`/lessons-gc` dedup)

The repo ships **data-free**: just the framework plus a handful of generic example notes (e.g. *"never force-push a shared branch"*, *"cap LLM API costs"*). See [`docs/`](docs/) for **SETUP**, **CONCEPTS**, **VAULT**, **COMMANDS**, and [`docs/examples/os-dashboard.md`](docs/examples/os-dashboard.md) for a sample dashboard.

---

## Cost & privacy

**$0. Local. Yours.** Personal OS never uses an API key. All inference runs on your own machine and **your data never leaves your laptop.** It works across **all** your projects, not one repo. The vault is plain markdown you own — no database, no cloud, no lock-in.

---

## FAQ

**Do I need API keys?** No. Never. All recall runs locally via `qmd vsearch`. There is no cost path.

**Does it work on Windows?** Yes, via WSL. Native targets are macOS and Linux.

**Can I use my existing Obsidian vault?** Yes — the vault is just an Obsidian-style markdown folder. The installer won't clobber existing `~/.claude` settings; point the index at your own vault if you prefer.

**What if I skip graphify / ollama?** Both are optional. Without graphify you lose structural (graph) recall but keep full semantic recall. Without ollama you lose only the dedup pass in `/lessons-gc`. qmd is the one required dependency.

**Is my data sent anywhere?** No. Inference is local and the vault stays on your machine. Nothing is uploaded.

**Is it bilingual?** Yes. Semantic recall uses multilingual Qwen3 embeddings, so your notes can be in any language and recall works *across* languages.

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
