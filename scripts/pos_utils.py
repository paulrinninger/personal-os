#!/usr/bin/env python3
"""pos_utils.py — shared foundations for all Personal OS scripts ($0, stdlib only).

write_atomic()       tmp file in the target dir + os.replace → never a half-written file
acquire/release_lock mkdir lock under <PERSONAL_OS_HOME>/locks/<name>.lock.d. The shell
                     wrappers carry a small mirror snippet using the SAME lock directory,
                     so shell and Python contend correctly against each other.
                     Stale-steal: a lock older than stale_hours OR whose PID is dead
                     gets taken over.
fire_log_append()    append one JSONL record to the fire-log (hits AND misses — see the
                     `type` field: hit | zero | timeout | error | no_qmd)
fire_log_compact()   rotation: atomically drop lines older than N days (nightly)

mkdir instead of flock: macOS ships no flock(1) CLI, mkdir is atomic on APFS/ext4 and
works identically from sh and Python.

Config (env, all optional):
  PERSONAL_OS_HOME      state home (locks, fire-log)   (default ~/.claude/personal-os)
  PERSONAL_OS_FIRE_LOG  fire-log path                  (default <state home>/lesson-fires.jsonl)
"""
from __future__ import annotations
import datetime as dt
import json
import os
import time

PO = os.path.expanduser(os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os"))
LOCK_ROOT = os.path.join(PO, "locks")
FIRE_LOG = os.path.expanduser(
    os.environ.get("PERSONAL_OS_FIRE_LOG", os.path.join(PO, "lesson-fires.jsonl")))


def write_atomic(path: str, data) -> None:
    """str → write as text; anything else → JSON. Always tmp + os.replace."""
    path = os.path.abspath(os.path.expanduser(path))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            if isinstance(data, str):
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False, indent=1)
        os.replace(tmp, path)
    finally:
        try:
            if os.path.exists(tmp):
                os.unlink(tmp)
        except OSError:
            pass


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _lock_path(name: str) -> str:
    return os.path.join(LOCK_ROOT, name + ".lock.d")


def _lock_is_stale(path: str, stale_hours: float) -> bool:
    try:
        pid = int(open(os.path.join(path, "pid"), encoding="ascii").read().strip())
        if not _pid_alive(pid):
            return True
    except Exception:
        pass  # no/unreadable pid file → fall back to the age criterion only
    try:
        return (time.time() - os.path.getmtime(path)) > stale_hours * 3600
    except OSError:
        return False


def acquire_lock(name: str, stale_hours: float = 6.0, wait_secs: float = 0) -> bool:
    """True = the lock is ours. Stale locks (dead PID or older than stale_hours) are
    taken over; the rmdir race is harmless (only one contender wins the next mkdir)."""
    os.makedirs(LOCK_ROOT, exist_ok=True)
    path = _lock_path(name)
    deadline = time.time() + wait_secs
    while True:
        try:
            os.mkdir(path)
            write_atomic(os.path.join(path, "pid"), str(os.getpid()))
            return True
        except FileExistsError:
            if _lock_is_stale(path, stale_hours):
                try:
                    pf = os.path.join(path, "pid")
                    if os.path.exists(pf):
                        os.unlink(pf)
                    os.rmdir(path)
                except OSError:
                    pass
                continue
        if time.time() >= deadline:
            return False
        time.sleep(2)


def release_lock(name: str) -> None:
    path = _lock_path(name)
    try:
        pf = os.path.join(path, "pid")
        if os.path.exists(pf):
            os.unlink(pf)
        os.rmdir(path)
    except OSError:
        pass


def fire_log_append(record: dict, fire_log: str = None) -> None:
    """Append-only, fail-open. Every record should carry a `type`:
    hit | zero (searched, nothing above threshold) | timeout | error | no_qmd."""
    log = fire_log or FIRE_LOG
    try:
        rec = dict(record)
        rec.setdefault("ts", dt.datetime.now().isoformat(timespec="seconds"))
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def fire_log_compact(days: int = 180, fire_log: str = None) -> int:
    """Atomically drop lines older than `days`; unparseable lines are KEPT (caution
    over eagerness). There is a small race window against parallel hook appends
    (~ms) — negligible for a nightly run. Returns the number of dropped lines."""
    log = fire_log or FIRE_LOG
    if not os.path.exists(log):
        return 0
    cutoff = dt.datetime.now() - dt.timedelta(days=days)
    keep, dropped = [], 0
    if not acquire_lock("fire-log", stale_hours=1.0):
        return 0
    try:
        for line in open(log, encoding="utf-8", errors="replace"):
            s = line.rstrip("\n")
            if not s.strip():
                continue
            try:
                ts = dt.datetime.fromisoformat(json.loads(s).get("ts", ""))
                if ts < cutoff:
                    dropped += 1
                    continue
            except Exception:
                pass
            keep.append(s)
        if dropped:
            write_atomic(log, "\n".join(keep) + ("\n" if keep else ""))
    finally:
        release_lock("fire-log")
    return dropped
