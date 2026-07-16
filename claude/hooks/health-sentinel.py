#!/usr/bin/env python3
"""SessionStart hook (matcher: startup): two small jobs, both fail-open, <1s.

1) BACKSTOP for "the scheduler itself is dead": the nightly jobs report their own
   health (pos_health.py finalize) — but if launchd/cron never starts them, nobody
   reports anything. This hook reads <PERSONAL_OS_HOME>/health.json (one small file,
   no network, no model) and shows a systemMessage ONCE per day on degradation or
   silence. Deliberately on SessionStart, not per prompt — zero latency in the
   working flow.

2) qmd WARMUP: the embedding model is pulled into the page cache detached (mmap),
   so the session's first real recall doesn't run into the cold-start timeout.
   No daemon, no port — just a throwaway process.

Config (env, optional): PERSONAL_OS_HOME (default ~/.claude/personal-os),
PERSONAL_OS_SCRIPTS_DIR (unused directly, kept for symmetry with the other hooks).
"""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys

MARKER = os.path.join(
    os.environ.get("TMPDIR", "/tmp"),
    "personal-os-health-sentinel-" + dt.date.today().isoformat())
HEALTH = os.path.join(
    os.path.expanduser(os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os")),
    "health.json")
STALE_HOURS = 30


def warmup():
    qmd = shutil.which("qmd") or "/opt/homebrew/bin/qmd"
    if not os.path.exists(qmd):
        return
    try:
        subprocess.Popen([qmd, "vsearch", "warmup", "-n", "1"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except Exception:
        pass


def main():
    warmup()
    if os.path.exists(MARKER):
        return
    try:
        health = json.load(open(HEALTH, encoding="utf-8"))
    except Exception:
        return  # no health.json yet (nightly jobs not scheduled) → nothing to report
    problems = []
    newest = None
    for name, j in (health.get("jobs") or {}).items():
        try:
            end = dt.datetime.fromisoformat(j.get("end", ""))
            newest = end if newest is None or end > newest else newest
        except Exception:
            pass
        if not j.get("ok"):
            bad = [s["name"] for s in j.get("steps", []) if s.get("rc")]
            problems.append(f"{name} ({', '.join(bad[:3]) or 'no steps'})")
    if newest is not None and (dt.datetime.now() - newest).total_seconds() > STALE_HOURS * 3600:
        problems.append(f"no nightly run since {newest:%Y-%m-%d %H:%M} (scheduler?)")
    doc = health.get("doctor") or {}
    if doc.get("verdict") == "FAIL":
        problems.append(f"doctor FAIL ({doc.get('fail')})")
    if not problems:
        return
    try:
        open(MARKER, "w").close()
    except Exception:
        pass
    print(json.dumps({"systemMessage":
        "⚠️ Personal OS degraded: " + " · ".join(problems)[:300]
        + " — details: health.json in PERSONAL_OS_HOME, or /os doctor"}))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
