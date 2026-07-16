"""save_nudge.sh (Stop hook) — real subprocess runs against fixture transcripts:
saved-session suppression, substantive enqueue, session-id dedup."""
import json
import os
import shutil
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(REPO, "scripts", "save_nudge.sh")

pytestmark = pytest.mark.skipif(
    shutil.which("jq") is None or shutil.which("sh") is None,
    reason="save_nudge.sh needs jq and sh")


def run_hook(tmp_path, sid, transcript_text, run_id="r1"):
    """Invoke the hook exactly like Claude Code does: hook JSON on stdin."""
    tp = tmp_path / f"transcript-{sid}-{run_id}.jsonl"
    tp.write_text(transcript_text, encoding="utf-8")
    tmpdir = tmp_path / f"tmp-{run_id}"          # fresh TMPDIR per run (marker isolation)
    tmpdir.mkdir(exist_ok=True)
    env = dict(os.environ,
               PERSONAL_OS_HOME=str(tmp_path / "po"),
               PERSONAL_OS_VAULT=str(tmp_path / "vault"),
               PERSONAL_OS_LOG_DIR=str(tmp_path / "logs"),
               PERSONAL_OS_LANG="en",
               TMPDIR=str(tmpdir))
    payload = json.dumps({"session_id": sid, "transcript_path": str(tp),
                          "cwd": str(tmp_path)})
    out = subprocess.run(["/bin/sh", SCRIPT], input=payload, text=True,
                         capture_output=True, env=env, timeout=30)
    return out, tmp_path / "po" / "harvest-queue.jsonl"


def edit_line():
    return '{"name":"Edit","input":{"file_path":"src/app.py"}}\n'


def vault_log_write_line(tmp_path):
    p = tmp_path / "vault" / "logs" / "2026-01-01-session.md"
    return '{"name":"Write","input":{"file_path":"%s"}}\n' % p


def test_saved_session_is_suppressed(tmp_path):
    # A session that wrote a real vault log via /save: neither enqueue nor nudge.
    transcript = edit_line() + vault_log_write_line(tmp_path)
    out, queue = run_hook(tmp_path, "sid-saved-001", transcript)
    assert out.returncode == 0
    assert out.stdout.strip() == ""
    assert not queue.exists()


def test_mere_mention_of_logs_path_does_not_suppress(tmp_path):
    # 0.2.0 regression guard: a logs/ path in prose (no file_path write) must NOT
    # suppress — the session still gets enqueued.
    transcript = edit_line() + "the docs mention vault/logs/2026-01-01-x.md somewhere\n"
    out, queue = run_hook(tmp_path, "sid-mention-01", transcript)
    assert queue.exists()
    assert "sid-mention-01" in queue.read_text()


def test_substantive_session_is_enqueued(tmp_path):
    out, queue = run_hook(tmp_path, "sid-work-0001", edit_line())
    assert out.returncode == 0
    assert queue.exists()
    rows = [json.loads(l) for l in queue.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
    assert rows[0]["session_id"] == "sid-work-0001"
    assert rows[0]["transcript_path"].endswith(".jsonl")


def test_pure_read_session_is_not_enqueued(tmp_path):
    transcript = '{"name":"Read","input":{"file_path":"README.md"}}\n'
    out, queue = run_hook(tmp_path, "sid-read-0001", transcript)
    assert not queue.exists()


def test_sid_dedup_across_runs(tmp_path):
    # Same session id firing Stop twice (fresh TMPDIR each time, so the marker file
    # can't mask the queue-level dedup): still exactly one queue entry.
    _, queue = run_hook(tmp_path, "sid-dup-00001", edit_line(), run_id="a")
    _, queue = run_hook(tmp_path, "sid-dup-00001", edit_line(), run_id="b")
    rows = [l for l in queue.read_text().splitlines() if l.strip()]
    assert len(rows) == 1
