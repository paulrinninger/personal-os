# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Nightly "dreaming" pass** (`scripts/dream.py` + `scripts/dream_run.sh`, `/dream` command,
  `install.py --schedule-dream`): an optional third nightly job that consolidates the vault while
  you sleep — condenses yesterday's residue, proposes `[[wikilinks]]` between notes that never
  reference each other, pre-chews lesson merge/cross-link candidates for `/lessons-gc`, surfaces
  firing-pattern observations from the recall hooks, and ranks the review inbox against your
  active projects. Writes exactly one suggestions-only note per night to `_inbox/dreams/`; never
  edits a live note. Only its residue pass touches an LLM at all (hard-capped call count); the rest
  is qmd/embeddings-only, $0. Requires Ollama; separate opt-in from `--schedule` since it makes
  real (if capped) LLM calls. Feedback from `/dream review` adaptively tunes each pass's
  thresholds/caps over time (counters only, no ML). New `os_doctor.py` check reports whether it's
  running.
- **ChatGPT export import** (`scripts/chatgpt_to_obsidian.py`): converts a ChatGPT data export
  (zip) into the vault (`chats/gpt/`), one note per conversation, incrementally — same rule-based,
  $0 tagging as `claude_to_obsidian.py`. Reads the zip directly (no extraction). Manual, one-off
  tool, not part of the nightly scheduler; `/mine-chats` was extended to also watch `chats/gpt/`.
- **`vault_autopush.sh`** + Stop-hook wiring: commits and pushes any pending vault changes to its
  git remote at the end of every session, not just at the next scheduled graph rebuild. No-op if
  the vault isn't a git repo with a remote configured.

## [0.2.0] - 2026-06-24

### Added

- **Auto-harvest loop.** The Stop hook (`save_nudge.sh`) now enqueues sessions that did real work (an
  Edit/Write/Bash action) but ended **without `/save`** to a harvest queue; the new `/harvest` command
  distills their lessons & ideas into a review inbox (`~/vault/_inbox/`, kept outside the qmd collection
  so un-reviewed drafts don't pollute recall) for Y/N promotion. Interactive, `$0`, no headless LLM — it
  closes the capture gap for sessions you forgot to save.
- **Runtime self-health doctor** (`claude/personal-os/os_doctor.py`) + `/os doctor` — deterministic,
  `$0`, read-only checks that the OS's own machinery is alive (recall hooks firing, qmd index fresh,
  lessons not rotting, harvest queue/inbox drained). Optional features (nightly scheduler, vault git
  backup) degrade to INFO so a fresh install reports clean; exit 1 only on a real failure. Also run by
  the nightly graph rebuild. Distinct from the one-time post-install `install/doctor.py`.
- `risk-recall.py` now also surfaces lessons before `git commit` and `git add -A|--all|-u|.`, not just
  `git push` — so staging/commit mistakes are caught at the moment they happen.

### Fixed

- **Save-detection false positive** in `scripts/save_nudge.sh`: the `/save` nudge keyed on any mention
  of a `logs/` path (matching CLAUDE.md, recall context, or the `/save` docs), so it could wrongly
  conclude a session was already saved and stay silent. It now matches a real `"file_path"` **write** to
  a vault `logs/*.md`.

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

[0.2.0]: https://keepachangelog.com/en/1.1.0/
[0.1.0]: https://keepachangelog.com/en/1.1.0/
