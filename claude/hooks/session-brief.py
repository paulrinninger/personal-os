#!/usr/bin/env python3
"""SessionStart hook (startup): project brief — the session starts knowing, not asking.

Recall used to be purely reactive (prompt / risk gate). This hook makes it proactive:
at session start it injects <=25 lines — hub status, open items from the newest
session log, top-3 lessons for the project. /resume becomes unnecessary for the
common case.

Project detection (first hit wins, otherwise silent):
 1. cwd prefix match against the `path:` frontmatter of the hubs (<vault>/projects/*.md)
    — authoritative
 2. slug match: cwd basename <-> hub file name
 3. un-hubbed fallback: newest log in <vault>/logs/ (or <vault>/*/logs/) whose name
    carries the cwd basename
Fail-open, latency budget <4.5s (one qmd call, 4s cap).

Config (env, all optional): PERSONAL_OS_VAULT, PERSONAL_OS_SCRIPTS_DIR.
"""
import datetime as dt
import glob
import json
import os
import re
import sys

VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
MAX_LINES = 25
STALE_DAYS = 14

sys.path.insert(0, os.path.expanduser(
    os.environ.get("PERSONAL_OS_SCRIPTS_DIR", "~/.personal-os/scripts")))
try:
    import pos_utils
    import qmd_search
except Exception:
    pos_utils = qmd_search = None


def norm(s):
    return re.sub(r"[-_\s]+", "", s.lower())


def find_hub(cwd):
    """(hub_path, slug) or (None, None)."""
    cands = []
    for f in glob.glob(os.path.join(VAULT, "projects", "*.md")):
        try:
            head = open(f, encoding="utf-8", errors="replace").read(2000)
        except Exception:
            continue
        m = re.search(r"^path:\s*(.+)$", head, re.M)
        if m:
            p = os.path.expanduser(m.group(1).strip().strip('"'))
            if p and (cwd == p or cwd.startswith(p.rstrip("/") + "/")):
                cands.append((len(p), f))
    if cands:
        return max(cands)[1], os.path.basename(max(cands)[1])[:-3]
    base = norm(os.path.basename(cwd))
    for f in glob.glob(os.path.join(VAULT, "projects", "*.md")):
        slug = os.path.basename(f)[:-3]
        if base and (norm(slug) in base or base in norm(slug)):
            return f, slug
    return None, None


def newest_log(slug_or_base):
    """Newest log carrying the slug in its name (central + per-project folders)."""
    pat = norm(slug_or_base)
    hits = []
    for f in glob.glob(os.path.join(VAULT, "logs", "*.md")) + \
            glob.glob(os.path.join(VAULT, "*", "logs", "*.md")):
        if pat and pat in norm(os.path.basename(f)):
            hits.append((os.path.getmtime(f), f))
    return max(hits)[1] if hits else None


def section(text, heading):
    m = re.search(rf"^##\s*{heading}[^\n]*\n(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1).strip() if m else ""


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    cwd = data.get("cwd") or os.getcwd()
    if cwd.rstrip("/") in (os.path.expanduser("~"), "/tmp", "/private/tmp", ""):
        return
    hub, slug = find_hub(cwd)
    logf = newest_log(slug or os.path.basename(cwd))
    if not hub and not logf:
        return  # quiet by design

    lines = []
    label = slug or os.path.basename(cwd)
    lines.append(f"PROJECT BRIEF {label} (Personal OS, automatic — sources inline):")

    if hub:
        try:
            t = open(hub, encoding="utf-8", errors="replace").read(4000)
            # hub template writes '**Stand (…) / Status:** <1-2 sentences>'
            m = re.search(r"\*\*(?:Stand|Status)[^*]*\*\*:?\s*(.+?)(?:\n\n|\n\*\*|\Z)", t, re.S)
            if m:
                stand = " ".join(m.group(0).split())[:400]
                lines.append(f"• {stand}")
        except Exception:
            pass

    if logf:
        age = (dt.datetime.now() - dt.datetime.fromtimestamp(os.path.getmtime(logf))).days
        if age <= STALE_DAYS:
            try:
                body = open(logf, encoding="utf-8", errors="replace").read(12000)
                off = section(body, r"(?:Offen|Open|Pending)")
                bullets = [l.strip() for l in off.splitlines() if l.strip().startswith("-")][:6]
                if bullets:
                    lines.append(f"• Open (from {os.path.basename(logf)}):")
                    lines += [f"   {b[:120]}" for b in bullets]
            except Exception:
                pass

    if hub and qmd_search:
        title = os.path.basename(hub)[:-3].replace("-", " ")
        res = qmd_search.vsearch(title, n=6, timeout=4)
        if res["outcome"] == "ok":
            tops = [h for h in res["hits"] if h["path"].startswith("lessons/")][:3]
            if tops:
                lines.append("• Relevant lessons: "
                             + " · ".join(f"{VAULT}/{h['path']} ({h['score']}%)" for h in tops))
        elif pos_utils:
            pos_utils.fire_log_append({"type": res["outcome"], "trigger": "SessionStart",
                                       "prompt": label[:60], "error": res["error"]})

    if len(lines) <= 1:
        return
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart",
        "additionalContext": "\n".join(lines[:MAX_LINES]),
    }}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
