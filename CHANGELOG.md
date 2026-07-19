# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0] - 2026-07-19

**Why this release exists, honestly:** 0.3's dreaming engine asked for permission every
night — one suggestions note, checkboxes, `/dream review`. The adoption telemetry was
unambiguous: the proposal notes accumulated and zero were ever reviewed. Asking was the
bug. 0.4 inverts the contract for the risk-free tier only — execute silently, journal
every action with verbatim undo data, and make rolling a whole night back cheaper than
a single approval ever was. Safety moves from up-front approval (which never happened)
to post-hoc undo (which takes under a minute).

### Added

- **Action journal + undo — the trust foundation** (`scripts/pos_actions.py`, `/undo`):
  every autopilot action is journaled to `<state home>/actions.jsonl` with verbatim
  undo data before you ever see it. Five undo ops (`remove_lines`, `move`,
  `set_status`, `remove_state_line`, `requeue`), each with precondition checks — what
  you already changed yourself is skipped, never clobbered. Undoing a link that
  *created* a `## Links` section also removes the then-empty heading (verbatim
  roundtrip). Every undo automatically writes `rejected` feedback; a nightly implicit
  scanner (`collect-feedback`, 48h–30d grace, sidecar against double-scoring) turns
  what you silently *did* with the artifacts into accepted/rejected signals for the
  same adaptive thresholds `/dream review` used to feed.
- **Silent autopilot executors** (`scripts/pos_autopilot.py`, wired into
  `dream_run.sh`): `act-links` (reciprocal wikilinks from the connections pass, cap
  6/night, curated dirs only, 30-min mtime guard against concurrent edits),
  `act-dreams` (dream notes >3d → `status: superseded`), `act-refs` (refs cards >21d
  outside the top 30 → `_inbox/refs/_archive/`, only `status: inbox|parked` — unknown
  provenance is never touched; `--dry-run` preview), `act-mine` (chat-mining drain,
  cap 10/night, both `chats/code` and `chats/gpt`), `act-harvest` (harvest-queue
  drain, cap 5/night; feeds the judge *parsed transcript text* instead of raw JSON,
  strict "when in doubt: NO" classifier, meta-phrase garbage filter EN+DE, qmd dedupe
  ≥80) and `notify` (ONE debounced morning notification). Kill switch:
  `<state home>/autopilot.off` — execution stops, passes keep computing. Never
  autonomous: deleting, curated note bodies (beyond the `## Links` append), `chats/`
  raw files, `profile/`, promoting its own drafts.
- **Guard compiler — deterministic PreToolUse guardrails** (`claude/hooks/guard.py` +
  `guards.example.json`): the top-firing deploy/git lessons compiled from text hints
  into real `deny`/`ask`/`warn` decisions — ten rules from the five top lesson
  families, seven named probes (multi-worktree, dirty tree, `.env` without
  `.vercelignore`, wrong author, behind-origin, stale preflight, pre-staged index).
  Probes are functions in code, never shell strings from JSON (no injection vector).
  Fail-open everywhere; `POS_GUARD=skip` prefix downgrades deny→ask (logged, never a
  silent allow); `mode: ask-only` for a shadow week before enforcing. Every fire lands
  in the fire-log (`guard-deny|guard-ask|guard-warn`) → visible in `/os`. The
  `deploy-wrong-author` rule reads its expected email from the rule config
  (`author_email`) — the repo ships only an empty placeholder, the installer fills it
  from the new `git_author_email` config key / `--git-author-email` flag.
- **Preflight stamp** (`scripts/preflight.sh`): full `tsc --noEmit` (main tsconfig,
  not `tsconfig.app.json`) + author check, stamped to `.git/pos-preflight-ok` with the
  HEAD SHA — the `deploy-no-preflight` guard rule demands a fresh marker (same SHA,
  <30 min) before push/deploy.
- **SessionStart project brief** (`claude/hooks/session-brief.py`): ≤25 lines injected
  at session start — hub status (authoritative `path:` frontmatter match, slug
  fallback, un-hubbed newest-log fallback), open items from the newest log (stale-skip
  after 14d), top-3 lessons via one capped qmd call. Sessions start knowing instead of
  asking; quiet by design in `~` and `/tmp`.
- **`/undo` and `/ask` commands**; **`scripts/os_dashboard.py`** — the deterministic
  one-code-path refresh for the `os:auto` block in `HOME.md` (`/os update` now calls
  it instead of hand-writing the block), including pipeline numbers, last night's
  autopilot activity, and system health.
- **Tests**: four new suites (54 tests — journal/undo byte-identical roundtrips for
  all five ops + precondition skips, guard decisions against real fixture git repos
  incl. ask-only/skip/fail-open and a hard PII assert on `guards.example.json`,
  autopilot executors with monkeypatched scoring, session-brief detection paths).
  Still no qmd/ollama/network anywhere in CI.

### Changed

- **The dream note is a journal now, not a todo list** (`scripts/dream.py` report):
  leads with "Executed tonight" (grouped actions + `/undo` hint), `status: journal`,
  no checkboxes, no block IDs. Suggestion lists below the thresholds are discarded
  instead of accumulated; connection suggestions no longer appear as todos (the
  autopilot executes the ones above threshold). gc/fires/triage/ventures shrink to
  hint lines; `/dream review` is retired — `/dream` shows, `/undo` reverts.
- **Doctor reframed around the drain** (`os_doctor.py`): new Autopilot check
  (`autopilot.off` → INFO "intentional", missing journal → INFO on fresh installs,
  stale journal → WARN), harvest-queue and chat-mining thresholds now measure
  "growing faster than the nightly drain?" (80/160) instead of nagging about backlogs
  the autopilot drains anyway.
- **Installer/uninstaller**: hooks `guard.py` + `session-brief.py` installed and
  sentinel-tracked (guard runs FIRST in the PreToolUse Bash group, the brief under
  SessionStart); `guards.json` materialized once from the example (never overwrites
  yours). Uninstall removes the new hooks/commands but deliberately leaves
  `guards.json` (your rules) and `actions.jsonl` + `harvest-queue-done.jsonl` (the
  undo journal — deleting it would take away rollback for actions already taken).

## [0.3.0] - 2026-07-16

### Added

- **Nightly dreaming engine** (`scripts/dream.py` + `scripts/dream_run.sh` + `/dream`,
  `install.py --schedule-dream`): once a night (04:45, ~30min after the graph rebuild,
  low-priority) the vault consolidates itself — eight passes: firing patterns (incl. recall
  *misses*), producer, missing `[[connections]]`, lesson-GC digest, venture patterns, inbox
  triage, yesterday's residue, report. Only the residue pass **must** use an LLM (small local
  model, hard-capped calls; ventures may add a single call to phrase its verdict) — the rest is
  qmd/embeddings/pure Python, $0. Output is a single suggestions-only note under
  `<vault>/_inbox/dreams/`; nothing ever edits a live note. `/dream review` walks it and each
  Y/N feeds adaptive per-pass thresholds (counters, no ML). Kill switch (`dream.off`), RAM
  pre-flight, per-pass resume with torn-file detection, mkdir lock, pass-state retention
  (owner-only dirs, pruned after 7 days). Requires Ollama for the embedding/LLM passes; the
  LLM-free ones run without it.
- **Two dreaming passes with outward reach: `ventures` and `producer`** (+ `/producer` command).
  `ventures` checks brand-new project hubs against your own past `done`/`parked` projects for a
  shared "shape", using embeddings plus a transitive similarity check (candidate siblings must
  also resemble *each other*, not just the new project) to keep false positives out — capped at
  one pattern a night. `producer` renders cold-outreach drafts from a `producer-queue.jsonl` you
  fill in yourself (required fields `id`, `observation`/`pain_point` — the latter two never
  invented) against `producer-templates.json`, pure `str.format()`, no LLM call. Since
  `dream.py` runs as a cron script with no MCP access, real Gmail drafts are only ever created
  by `/producer review` — never sent, separate feedback channel (`producer-feedback.jsonl`) so
  draft verdicts don't skew the other passes' thresholds. Example configs:
  `config/producer-*.example.*`.
- **Adversarial bug-audit of the ventures/producer passes** (5 rounds): fixed a cursor bug where
  `ventures` silently marked candidate hubs "checked" without ever evaluating them once its
  nightly cap was hit; a cluster-search bug that could miss a valid sibling pair not anchored to
  the top match; a bug where the `producer` lead queue was never drained, so any unreviewed
  entry re-rendered into a new duplicate draft every night; non-atomic pass-state writes that a
  killed run could leave torn (silently read back as "already done"); a producer-templates parse
  error that looked identical to "nothing queued tonight"; world-readable permissions on the
  pass-state directory (now owner-only for new folders); and `/producer review`'s and
  `/dream review`'s accept/reject feedback never actually reaching `adaptive_params()`. Each
  finding independently reproduced before fixing.
- **Risk-tiered confirmation for `/dream review` and `/lessons-gc`**: purely additive,
  trivially-reversible actions (reciprocal wikilinks, deadline extensions) run automatically but
  are always reported; anything that changes real content (merges, rule corrections, archiving,
  promotions) still needs an explicit yes — presented as ONE concrete proposal, not a
  two-round "should I?" dance. Both commands close with a mandatory count-check so no checkbox
  is silently skipped.
- **ChatGPT import** (`scripts/chatgpt_to_obsidian.py`): converts a ChatGPT data-export zip into
  one markdown note per conversation under `chats/gpt/` — reads the JSON shards straight out of
  the zip (no extraction), recovers the canonical thread via parent pointers, drops thinking
  traces. Rule-based tagging, $0, incremental across exports via an atomically-written state
  file. Manual one-off, not part of the nightly scheduler. `/mine-chats` now mines
  `chats/code/` **and** `chats/gpt/` (default batch 10).
- **Opt-in vault autopush** (`scripts/vault_autopush.sh`, `install.py --autopush`): commit+push
  the vault to its own private remote at session end (Stop hook) and from the nightly — one code
  path. **Allowlist staging** (never `git add -A`), sensitive-path abort, mkdir lock, commit-rc
  check, stray warnings. The Stop hook is appended programmatically at install time instead of
  shipping unconditionally in the settings fragment.
- **Health signal** (`scripts/pos_health.py`): the fail-open nightly wrappers now mirror every
  step's rc/duration into a machine-readable `health.json`; degradation is delivered at most once
  per day as a desktop notification. New SessionStart hook `health-sentinel.py` backstops a dead
  scheduler and warms the qmd model against cold-start timeouts. `os_doctor.py` gained checks for
  nightly step failures, recall-miss rates, chat-mining backlog, unreviewed dream notes, refs
  queue, and autopush wiring — and records its verdict into `health.json`.
- **Shared foundations** (`scripts/qmd_search.py`, `scripts/pos_utils.py`): ONE qmd client
  (`vsearch --format json`, scores normalized 0–100, never raises) replaces four divergent
  hand-rolled parsers; shared atomic writes, mkdir locks with stale-steal, and fire-log
  append/compact used by hooks, dream engine, and doctors.
- **Miss-logging in the recall hooks**: `recall-lessons.py`/`risk-recall.py` now log zero-hit,
  timeout, and error outcomes (`type` field) alongside hits — recall precision and cold-start
  rates become measurable (`/os doctor`, dream `fires` pass). Fire counting everywhere skips
  non-hit records.
- **Install manifest + drift check**: `install.py` writes `install-manifest.json` (sha256 of every
  installed file); `install.py --check-drift` three-way-compares installed vs manifest vs repo
  ("in sync" / "update available" / "locally customized" / "conflict"). Maintainer counterpart:
  `scripts/dev_drift.sh`.
- **Test suite + CI**: `tests/` (pytest, stdlib mocks only — no qmd/ollama/network) covering the
  qmd JSON parser, the dream chats-cursor, ventures/producer registration + offline producer
  templating/queue-drain, atomic writes + locking, fire-log rotation, Stop-hook save detection,
  chat-import state atomicity, and the health engine; new GitHub Actions job
  `.github/workflows/tests.yml`.

### Fixed

- **Dream chats-cursor skip bug** (residue pass): new chats were sorted newest-first but the
  cursor advanced past ALL of them — anything beyond the per-night cap silently vanished from
  dreaming forever. Now FIFO with the cursor advancing only over the consumed slice. (The
  bug-audit round above fixed the analogous ventures cursor; this one in residue was still live.)
- **`dream_run.sh` word-splitting**: passes were invoked via an unquoted command string, breaking
  on a scripts dir containing spaces; each pass now calls `python3 "<dir>/dream.py"` directly.
- **Non-atomic state writes**: chat-import state files, the wikilink-injected `graph.json`, dream
  cursor/embed caches, and `health.json` are all written via tmp + `os.replace` (shared
  `pos_utils.write_atomic`) — a crash mid-write can no longer tear state apart.
- **Four divergent qmd parsers** (two hooks, dream connections pass, install doctor) collapsed
  into the shared JSON-mode client — the old `Score: N%` regexes would silently score everything
  0 on unexpected output.

### Security / Privacy

- **Vault scaffold `.gitignore` now excludes `chats/` and `_inbox/` entirely**: raw chat imports
  (complete private history) and un-reviewed drafts stay local, never in a remote — the review
  gate is the safety net.
- **Autopush uses allowlist staging instead of `git add -A`** and became opt-in: a denylist fails
  open on every new sensitive folder; the allowlist fails closed, plus a belt-and-braces abort if
  `chats/`/`_inbox/` ever reach the index.
- **Dream pass state is short-lived and private**: `dream-work/` date folders are created
  owner-only (0700) and pruned after 7 days — they can hold real lead names and venture-verdict
  text.

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

[0.3.0]: https://keepachangelog.com/en/1.1.0/
[0.2.0]: https://keepachangelog.com/en/1.1.0/
[0.1.0]: https://keepachangelog.com/en/1.1.0/
