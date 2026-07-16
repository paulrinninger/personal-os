"""pos_utils — atomic writes and the mkdir lock (mutual exclusion + stale steal)."""
import json
import os
import subprocess
import time

import pos_utils


# ---------------------------------------------------------------- write_atomic

def test_write_atomic_str(tmp_path):
    p = tmp_path / "sub" / "file.txt"     # parent dir doesn't exist yet
    pos_utils.write_atomic(str(p), "hello\n")
    assert p.read_text(encoding="utf-8") == "hello\n"
    # no tmp litter left behind
    assert [f for f in os.listdir(p.parent) if ".tmp." in f] == []


def test_write_atomic_obj_is_json(tmp_path):
    p = tmp_path / "state.json"
    pos_utils.write_atomic(str(p), {"a": 1, "b": [1, 2], "u": "ümlaut"})
    assert json.load(open(p, encoding="utf-8")) == {"a": 1, "b": [1, 2], "u": "ümlaut"}


def test_write_atomic_overwrites(tmp_path):
    p = tmp_path / "f"
    pos_utils.write_atomic(str(p), "one")
    pos_utils.write_atomic(str(p), "two")
    assert p.read_text() == "two"


# ------------------------------------------------------------------------ lock

def test_lock_mutual_exclusion(po_home):
    assert pos_utils.acquire_lock("job") is True
    # second acquisition (same live pid, fresh mtime) must fail immediately
    assert pos_utils.acquire_lock("job", wait_secs=0) is False
    pos_utils.release_lock("job")
    assert pos_utils.acquire_lock("job") is True
    pos_utils.release_lock("job")


def test_lock_release_is_idempotent(po_home):
    pos_utils.release_lock("never-acquired")  # must not raise


def test_stale_steal_dead_pid(po_home):
    # forge a lock held by a pid that is guaranteed dead
    proc = subprocess.Popen(["sleep", "0"])
    proc.wait()
    dead_pid = proc.pid
    d = os.path.join(pos_utils.LOCK_ROOT, "job.lock.d")
    os.makedirs(d)
    with open(os.path.join(d, "pid"), "w") as f:
        f.write(str(dead_pid))
    assert pos_utils.acquire_lock("job", wait_secs=0) is True  # stolen
    pos_utils.release_lock("job")


def test_stale_steal_old_mtime(po_home):
    d = os.path.join(pos_utils.LOCK_ROOT, "job.lock.d")
    os.makedirs(d)
    with open(os.path.join(d, "pid"), "w") as f:
        f.write(str(os.getpid()))   # our own (alive) pid — only age can free it
    old = time.time() - 10 * 3600
    os.utime(d, (old, old))
    assert pos_utils.acquire_lock("job", stale_hours=6.0, wait_secs=0) is True
    pos_utils.release_lock("job")


def test_fresh_lock_with_alive_pid_is_not_stolen(po_home):
    d = os.path.join(pos_utils.LOCK_ROOT, "job.lock.d")
    os.makedirs(d)
    with open(os.path.join(d, "pid"), "w") as f:
        f.write(str(os.getpid()))
    assert pos_utils.acquire_lock("job", stale_hours=6.0, wait_secs=0) is False
