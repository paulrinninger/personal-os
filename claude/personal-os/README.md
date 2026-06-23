# Personal OS — the lessons loop (local & $0)

Closes the learning loop over `~/vault/lessons/`:
**Capture → Recall → Apply → Measure → Prune → (better Capture)**

Capture = `/lesson`, `/save`, `/idea`, `/mine-chats`. The rest lives here:

## Recall (automatic — no need to remember)
- **`hooks/recall-lessons.py`** — `UserPromptSubmit` hook. On EVERY message: `qmd vsearch`
  (semantic, local) over the lessons; hits ≥58% are injected as context. Quiet when nothing matches.
- **`hooks/risk-recall.py`** — `PreToolUse` hook. Right BEFORE risky/outward actions (Bash:
  push/--force/rm -rf/reset --hard/deploy/db-drop/…, Mail: create_draft/send_*). Same recall logic,
  triggered at the failure moment. For mail it seeds the query with email-mechanics terms (not the
  body) so send-lessons reliably surface.
- Both append one line per injection to **`lesson-fires.jsonl`** (the measure data source).
- Wired in `~/.claude/settings.json` → `hooks.UserPromptSubmit` / `hooks.PreToolUse`.

## Measure + Prune
- **`os_lessons.py health`** — compact system health (for `/os`): total, ever/never fired, top
  firers, archive candidates, stale count. Instant (no embeddings).
- **`os_lessons.py gc`** — full report: archive candidates (never fired + >90 d), stale
  (`review_by` overdue), and similarity in two bands (via `nomic-embed-text` over ollama's public
  API — no qmd internals): **merge** (cosine ≥0.88 = true duplicate) vs **related/cross-link**
  (0.82–0.88 = only link, don't merge). Two bands, because "thematically close" ≠ "duplicate" —
  blind merging at 0.82 would destroy distinct rules. (ollama optional; without it, cold/stale only.)
- **`/lessons-gc`** (command) — runs `gc`, proposes merges/archive/re-validation, applies ONLY
  after a Y/N. Archive = move to `~/vault/_archive/lessons/` (outside the qmd collection → out of
  recall, but preserved), then `qmd update`. **Never delete.**

## Decay
- Time-sensitive lessons get `review_by: YYYY-MM-DD` (see `/lesson`). `gc` reports overdue ones
  for re-validation instead of treating them as true forever.

## Guiding principle
A lesson earns its place only if it fires. Never fired → archive. Fired often → sharpen.
Contradictory → merge. That keeps recall sharp instead of bloated.

## Tuning
- Threshold/mode: `PERSONAL_OS_SCORE`, `SEARCH_MODE` in the hook scripts.
- Risk triggers: `RISKY_BASH` / `MAIL_KEYS` in `risk-recall.py`.
- Duplicate threshold: `--dup-min` (default 0.82) / `--merge-min` (default 0.88).
- Injection log: `$PERSONAL_OS_LOG_DIR/hooks.log` (`[recall-lessons]` / `[risk-recall]`).
- Language of injected notes: `PERSONAL_OS_LANG` (`en` | `de`).
- Hooks on/off: `/hooks`.
