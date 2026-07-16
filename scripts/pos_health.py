#!/usr/bin/env python3
"""pos_health.py — health signal for the Personal OS nightly jobs ($0, stdlib).

The problem this solves: the nightly wrappers are deliberately fail-open (each step
runs via `run … || WARN`, wrapper exit is always 0) — the scheduler's LastExitStatus
is therefore worthless as a health signal, and failures live only as free text in
logs nobody reads. Here every step rc is mirrored into a machine-readable
<PERSONAL_OS_HOME>/health.json and degradation is delivered ONCE per day as a
desktop notification. The wrappers' fail-open semantics stay untouched (health
capture never changes control flow).

Subcommands (all fail-open, exit 0 — except `check`):
  begin <job>                     start a fresh step file (start marker)
  step <job> <label> <rc> <secs>  record one step
  finalize <job>                  merge steps → health.json; degraded → notification
  doctor-record <verdict> <fail> <warn> <ok>   record the doctor verdict (FAIL → notification)
  check                           one-liner + exit 1 if degraded/stale (sentinel/dashboard)

health.json: {"version":1, "jobs":{<job>:{start,end,ok,steps:[{name,rc,secs}]}},
              "doctor":{ts,verdict,fail,warn,ok}, "notified":{date,reason}}

Config (env, optional): PERSONAL_OS_HOME — state home (default ~/.claude/personal-os).
"""
from __future__ import annotations
import datetime as dt
import json
import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pos_utils

PO = pos_utils.PO
HEALTH = os.path.join(PO, "health.json")
STEPS_DIR = os.path.join(PO, "health")
STALE_HOURS = 30  # no job end younger than this → "the nightly did not run"


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _load() -> dict:
    try:
        d = json.load(open(HEALTH, encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def _save(d: dict) -> None:
    d.setdefault("version", 1)
    pos_utils.write_atomic(HEALTH, d)


def _steps_file(job: str) -> str:
    return os.path.join(STEPS_DIR, f"steps-{job}.jsonl")


def _notify(title: str, msg: str) -> None:
    """Best-effort desktop notification: osascript on macOS, notify-send elsewhere."""
    try:
        if platform.system() == "Darwin":
            subprocess.run(
                ["osascript", "-e",
                 'display notification "{}" with title "{}"'.format(
                     msg.replace('"', "'")[:200], title.replace('"', "'"))],
                capture_output=True, timeout=10)
        else:
            subprocess.run(["notify-send", title, msg[:200]],
                           capture_output=True, timeout=10)
    except Exception:
        pass


def _maybe_notify(d: dict, reason: str, msg: str) -> None:
    """At most one notification per calendar day (debounce lives in health.json)."""
    today = dt.date.today().isoformat()
    if (d.get("notified") or {}).get("date") == today:
        return
    _notify("Personal OS: nightly degraded", msg)
    d["notified"] = {"date": today, "reason": reason}


def cmd_begin(job: str) -> None:
    os.makedirs(STEPS_DIR, exist_ok=True)
    pos_utils.write_atomic(_steps_file(job), json.dumps({"_start": _now()}) + "\n")


def cmd_step(job: str, label: str, rc: str, secs: str) -> None:
    os.makedirs(STEPS_DIR, exist_ok=True)
    with open(_steps_file(job), "a", encoding="utf-8") as f:
        f.write(json.dumps({"name": label, "rc": int(rc), "secs": int(float(secs))},
                           ensure_ascii=False) + "\n")


def cmd_finalize(job: str) -> None:
    start, steps = None, []
    try:
        for line in open(_steps_file(job), encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if "_start" in r:
                start = r["_start"]
            elif "name" in r:
                steps.append({"name": r["name"], "rc": int(r.get("rc", 1)),
                              "secs": int(r.get("secs", 0))})
    except FileNotFoundError:
        pass
    failed = [s["name"] for s in steps if s["rc"] != 0]
    d = _load()
    d.setdefault("jobs", {})[job] = {
        "start": start, "end": _now(), "ok": not failed and bool(steps), "steps": steps,
    }
    if failed:
        _maybe_notify(d, f"{job}:steps",
                      f"{job}: {', '.join(failed[:4])}"
                      + (f" (+{len(failed) - 4})" if len(failed) > 4 else "")
                      + " failed — see the job log")
    _save(d)


def cmd_doctor_record(verdict: str, fail: str, warn: str, ok: str) -> None:
    d = _load()
    d["doctor"] = {"ts": _now(), "verdict": verdict,
                   "fail": int(fail), "warn": int(warn), "ok": int(ok)}
    if verdict == "FAIL":
        _maybe_notify(d, "doctor:FAIL", f"Doctor: {fail} FAIL — run /os doctor")
    _save(d)


def cmd_check() -> int:
    """Exit 1 if degraded (job failures / doctor FAIL / everything older than STALE_HOURS)."""
    d = _load()
    jobs = d.get("jobs") or {}
    problems = []
    newest = None
    for name, j in jobs.items():
        try:
            end = dt.datetime.fromisoformat(j.get("end", ""))
            newest = end if newest is None or end > newest else newest
        except Exception:
            pass
        if not j.get("ok"):
            bad = [s["name"] for s in j.get("steps", []) if s.get("rc")] or ["no steps"]
            problems.append(f"{name}: {', '.join(bad[:3])}")
    if not jobs:
        problems.append("no job data yet")
    elif newest is None or (dt.datetime.now() - newest).total_seconds() > STALE_HOURS * 3600:
        problems.append(f"no nightly run in >{STALE_HOURS}h (scheduler dead?)")
    doc = d.get("doctor") or {}
    if doc.get("verdict") == "FAIL":
        problems.append(f"doctor FAIL ({doc.get('fail')})")
    if problems:
        print("DEGRADED — " + " · ".join(problems))
        return 1
    age = f" (last run {newest:%F %H:%M})" if newest else ""
    print(f"OK — {len(jobs)} job(s) green{age}, doctor {doc.get('verdict', '?')}")
    return 0


def main() -> int:
    a = sys.argv[1:]
    try:
        if not a:
            print(__doc__)
            return 0
        if a[0] == "begin" and len(a) == 2:
            cmd_begin(a[1])
        elif a[0] == "step" and len(a) == 5:
            cmd_step(a[1], a[2], a[3], a[4])
        elif a[0] == "finalize" and len(a) == 2:
            cmd_finalize(a[1])
        elif a[0] == "doctor-record" and len(a) == 5:
            cmd_doctor_record(a[1], a[2], a[3], a[4])
        elif a[0] == "check":
            return cmd_check()
        else:
            print(f"pos_health: unknown: {' '.join(a)}", file=sys.stderr)
    except Exception as e:
        # fail-open: health bookkeeping must never break a nightly job
        print(f"pos_health: WARN {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
