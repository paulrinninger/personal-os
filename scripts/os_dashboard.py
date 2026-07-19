#!/usr/bin/env python3
"""os_dashboard.py — deterministic HOME.md dashboard refresh ($0, no LLM).

Replaces ONLY the block between <!-- os:auto:start --> and <!-- os:auto:end --> in
<vault>/HOME.md (+ the frontmatter `updated:` line). Run it nightly (the dream job
is a good host) AND as the engine behind `/os update` — one code path, so manual and
nightly refreshes can never diverge again. (Before: the block was hand-written by
`/os update`, went weeks without a run, and every number drifted low.)

The block also shows pipeline/system health (queues, job ages, doctor verdict) —
HOME.md becomes the one page that shows knowledge state AND system state.
Aborts LOUDLY if the markers are missing (never eat the file).

Config (env, all optional):
  PERSONAL_OS_VAULT  vault location  (default ~/vault)
  PERSONAL_OS_HOME   state home      (default ~/.claude/personal-os)
"""
from __future__ import annotations
import datetime as dt
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pos_utils

VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
HOME_MD = os.path.join(VAULT, "HOME.md")
START, END = "<!-- os:auto:start -->", "<!-- os:auto:end -->"
IDEA_KINDS = ("hooks", "video", "posting", "product")


def _count(pattern: str, recursive: bool = False) -> int:
    return len(glob.glob(os.path.join(VAULT, pattern), recursive=recursive))


def _stem(p: str) -> str:
    return os.path.splitext(os.path.basename(p))[0]


def _mining_backlog(sub: str, state_file: str) -> int:
    try:
        mined = sum(1 for l in open(os.path.join(VAULT, state_file),
                                    encoding="utf-8", errors="replace") if l.strip())
    except Exception:
        mined = 0
    return max(0, len(glob.glob(os.path.join(VAULT, "chats", sub, "*.md"))) - mined)


def _age_str(iso: str) -> str:
    try:
        h = (dt.datetime.now() - dt.datetime.fromisoformat(iso)).total_seconds() / 3600
        return f"{h:.0f}h" if h < 48 else f"{h / 24:.0f}d"
    except Exception:
        return "?"


def build_block() -> str:
    today = dt.date.today().isoformat()
    lessons = sorted(glob.glob(os.path.join(VAULT, "lessons", "*.md")),
                     key=os.path.getmtime, reverse=True)
    ideas = {k: _count(f"ideas/{k}/*.md") for k in IDEA_KINDS}
    knowledge = _count("knowledge/**/*.md", recursive=True)
    profile = _count("profile/*.md")

    hubs, active = [], []
    for f in sorted(glob.glob(os.path.join(VAULT, "projects", "*.md"))):
        hubs.append(f)
        try:
            if re.search(r"^status:\s*active", open(f, encoding="utf-8",
                                                    errors="replace").read(3000), re.M):
                active.append(_stem(f))
        except Exception:
            pass

    # pipeline numbers
    refs = [p for p in glob.glob(os.path.join(VAULT, "_inbox/refs/*.md"))
            if not os.path.basename(p).startswith(("_INDEX", "_DIGEST"))]
    # autopilot activity from last night (replaces any "n dreams unreviewed" guilt metric)
    auto_acts = auto_drafts = 0
    try:
        for line in open(os.path.join(pos_utils.PO, "actions.jsonl"), encoding="utf-8",
                         errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("night") == dt.date.today().isoformat() and \
                    r.get("action") not in ("undo", "undo.skipped"):
                auto_acts += 1
                if r["action"] == "draft.create":
                    auto_drafts += 1
    except FileNotFoundError:
        pass
    hq = os.path.join(pos_utils.PO, "harvest-queue.jsonl")
    harvest = sum(1 for l in open(hq, encoding="utf-8", errors="replace")
                  if l.strip()) if os.path.exists(hq) else 0
    mining = _mining_backlog("code", ".chat_mining_state.txt") + \
        _mining_backlog("gpt", ".chatgpt_mining_state.txt")

    # system health from health.json
    sysline = "Health: no job data yet (pos_health)"
    try:
        h = json.load(open(os.path.join(pos_utils.PO, "health.json"), encoding="utf-8"))
        parts = []
        for name, j in sorted((h.get("jobs") or {}).items()):
            parts.append(f"{name} {'ok' if j.get('ok') else 'WARN'} ({_age_str(j.get('end', ''))})")
        doc = h.get("doctor") or {}
        if doc.get("verdict"):
            parts.append(f"doctor {doc['verdict']}"
                         + (f" ({doc.get('warn')} WARN)" if doc.get("warn") else ""))
        if parts:
            sysline = "System: " + " · ".join(parts)
    except Exception:
        pass

    lines = [
        START,
        f"_As of: {today} (auto-refresh via os_dashboard.py · manual: /os update)_",
        "",
        "**Inventory:** {} lessons · {} ideas ({}) · {} knowledge notes · "
        "{} project hubs ({} active) · {} profile notes".format(
            len(lessons),
            sum(ideas.values()),
            ", ".join(f"{v} {k}" for k, v in ideas.items()),
            knowledge, len(hubs), len(active), profile),
        "",
        "**Newest lessons:**",
    ]
    lines += [f"- [[{_stem(p)}]]" for p in lessons[:5]]
    lines += [
        "",
        "**Active projects:** " + (" · ".join(f"[[{a}]]" for a in active) or "—"),
        "",
        "**Pipeline:** refs {} live · harvest queue {} · chat mining {} open — "
        "the autopilot drains these nightly".format(len(refs), harvest, mining),
        "**Autopilot:** {} actions last night ({} drafts in _inbox/lessons) · "
        "undo: `/undo` · off: `touch <state home>/autopilot.off`".format(
            auto_acts, auto_drafts),
        f"**{sysline}**",
    ]
    if os.path.isdir(os.path.join(VAULT, "graphify-out")):
        lines += ["",
                  "**Graph:** `graphify-out/graph.html` (vault) — rebuilt by the nightly graph job"]
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    try:
        text = open(HOME_MD, encoding="utf-8").read()
    except Exception as e:
        print(f"os_dashboard: ERROR — HOME.md not readable: {e}", file=sys.stderr)
        return 1
    if START not in text or END not in text or text.find(START) > text.find(END):
        print("os_dashboard: ERROR — os:auto markers missing/broken in HOME.md, "
              "nothing written (never eat the file)", file=sys.stderr)
        return 1
    pre = text[:text.find(START)]
    post = text[text.find(END) + len(END):]
    new = pre + build_block() + post
    new = re.sub(r"^updated:.*$", f"updated: {dt.date.today().isoformat()}", new,
                 count=1, flags=re.M)
    if new != text:
        pos_utils.write_atomic(HOME_MD, new)
        print(f"os_dashboard: HOME.md refreshed ({dt.date.today().isoformat()})")
    else:
        print("os_dashboard: no change")
    return 0


if __name__ == "__main__":
    sys.exit(main())
