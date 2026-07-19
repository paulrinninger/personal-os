---
description: "Personal OS dashboard: status across all projects — lessons, ideas, hubs, open items. 'update' refreshes the auto-block in HOME.md."
argument-hint: "[optional: 'update' | 'doctor' | a topic/domain to focus on, e.g. 'marketing']"
---

You give the user an overview of their Personal OS (`~/vault/`, rules: `~/vault/CLAUDE.md`).

**`doctor` mode** (`$ARGUMENTS` == `doctor`): run only the deterministic self-health check and stop — it
verifies the OS's own machinery is alive (recall hooks firing, qmd index fresh, lessons not rotting,
harvest queue drained, inbox reviewed):
```bash
python3 ~/.claude/personal-os/os_doctor.py
```
Show its output as-is; on WARN/FAIL add one line each on what to do (`/lessons-gc`, `/harvest`), else
"system healthy." This is the ongoing runtime check — distinct from the one-time `install/doctor.py`.

Steps:

1. Collect data (read-only, $0):
   ```bash
   ls -t ~/vault/lessons/*.md 2>/dev/null | head -5
   ls -t ~/vault/ideas/*/*.md 2>/dev/null | head -8
   grep -l "status: active" ~/vault/ideas/*/*.md 2>/dev/null | wc -l
   grep -H "^status:" ~/vault/projects/*.md 2>/dev/null
   ls -t ~/vault/*/logs/*.md ~/vault/logs/*.md 2>/dev/null | head -5
   ```
2. If `$ARGUMENTS` is a topic: additionally `grep -ril "<topic>" ~/vault/lessons ~/vault/ideas
   ~/vault/knowledge 2>/dev/null` and read the top hits. If `~/vault/graphify-out/graph.json`
   exists, you may instead use `graphify query "<topic>" --graph ~/vault/graphify-out/graph.json`.
2b. Lessons health (measure loop, $0):
   ```bash
   python3 ~/.claude/personal-os/os_lessons.py health 2>/dev/null
   ```
2c. Autopilot: `python3 ~/.personal-os/scripts/pos_actions.py list --night $(date +%F)`
   (or your scripts dir) — one line "Autopilot last night: n actions (x links, y
   archived, z drafts) — /dream for the journal, /undo to roll back".
2d. **Wins (7 days)** from `~/.claude/personal-os/lesson-fires.jsonl`: count type=hit
   (recall injections), type=guard-ask/guard-deny (risk commands actively intercepted,
   incl. the override:true share), top-3 guard rules. One section "What the OS
   prevented/did this week" — recall hits, guard stops, autopilot actions
   (actions.jsonl, 7d), drafts created. This is the trust evidence for acting silently.
3. Output, scannable (do not modify files, except step 4):
   - **Projects:** hubs with status != done — name + status line.
   - **Newest lessons (5):** title as a rule sentence.
   - **System health:** from step 2b — total, ever/never fired, top firers, archive
     candidates, stale count. If there is archive/stale/duplicate pressure:
     1 line "→ /lessons-gc due".
   - **Open ideas:** count per kind + the 5 newest titles.
   - **Recently worked on:** the 5 newest logs (project + date + title).
   - **Suggestion:** 1 line — what is worth doing next (from the open items).
4. ONLY if `$ARGUMENTS` == `update`: run
   `python3 ~/.personal-os/scripts/os_dashboard.py` (or your scripts dir) — THAT is
   the one code path for the os:auto block in `~/vault/HOME.md` (it can also run
   nightly; never hand-write the block, or manual and nightly numbers diverge again).
5. No git commit.
