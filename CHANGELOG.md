# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-06-23

Initial public release.

### Added

- **Persistent cross-project memory** for Claude Code in a plain-markdown vault (`~/vault`) the user owns — no database, no cloud, no lock-in. Core loop: Capture → Recall → Maintain.
- **Automatic recall via two hooks:**
  - `recall-lessons.py` (`UserPromptSubmit`) — runs a local semantic search (`qmd vsearch`, $0, no API) on every prompt and injects relevant past lessons into Claude's context.
  - `risk-recall.py` (`PreToolUse`) — fires before risky or outward actions (e.g. `git push --force`, `rm -rf`, `reset --hard`, deploys, `npm publish`, dropping a database, sending mail) and re-surfaces the lessons that matter at that moment.
- **Capture commands:** `/save` (dated session log + auto-harvest of lessons & ideas), `/lesson` (error + fix + why, with dedup), `/idea` (`hook` | `video` | `posting` | `product`).
- **Maintain commands:** `/os` (dashboard), `/lessons-gc` (prune cold/stale/duplicate lessons), `/mine-chats` (distill learnings from imported chat transcripts), `/resume` (rebuild context).
- **Two retrieval modes:** qmd for meaning (semantic; hybrid BM25 + vector + RRF + rerank; multilingual) and graphify for structure (knowledge graph; `query` / `path` / `explain` / `affected`). Both $0 and fully local.
- **Multilingual recall** powered by Qwen3 embeddings — notes can be in any language and recall works across languages.
- **Non-destructive installer** (`install/install.sh`) that creates `~/vault`, merges commands/hooks/skills into `~/.claude` without clobbering existing settings, writes the qmd index config, and builds the first index.
- **Data-free distribution:** ships only the framework plus a handful of generic example notes.
- **Documentation** under `docs/` (SETUP, CONCEPTS, VAULT, COMMANDS) and a sample dashboard at `docs/examples/os-dashboard.md`.

[0.1.0]: https://keepachangelog.com/en/1.1.0/
