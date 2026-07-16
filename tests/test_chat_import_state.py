"""claude_to_obsidian.py — incremental state round-trip + atomic state write."""
import json
import os
import sys
from pathlib import Path

import pytest

import claude_to_obsidian as cto


def transcript_lines():
    return "\n".join([
        json.dumps({"type": "user", "timestamp": "2026-01-01T10:00:00Z",
                    "cwd": "/w/proj-a", "gitBranch": "main",
                    "message": {"role": "user",
                                "content": "How do I fix the failing build step?"}}),
        json.dumps({"type": "assistant", "timestamp": "2026-01-01T10:01:00Z",
                    "message": {"role": "assistant",
                                "content": [{"type": "text",
                                             "text": "Pin the linker version."}]}}),
    ]) + "\n"


@pytest.fixture
def env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    vault.mkdir()
    projects = tmp_path / "claude-projects"
    (projects / "-w-proj-a").mkdir(parents=True)
    tp = projects / "-w-proj-a" / "abcdef123456.jsonl"
    tp.write_text(transcript_lines(), encoding="utf-8")
    monkeypatch.setattr(cto, "VAULT", vault)
    monkeypatch.setattr(cto, "OUT_DIR", vault / "chats" / "code")
    monkeypatch.setattr(cto, "STATE_FILE", vault / ".chat_import_state.json")
    monkeypatch.setattr(cto, "PROJECTS_DIR", projects)
    monkeypatch.setattr(sys, "argv", ["claude_to_obsidian.py"])
    return vault, tp


def test_import_writes_note_and_state(env):
    vault, tp = env
    assert cto.main() == 0
    notes = list((vault / "chats" / "code").glob("*.md"))
    assert len(notes) == 1
    assert "How do I fix the failing build step?" in notes[0].read_text(encoding="utf-8")
    state = json.loads((vault / ".chat_import_state.json").read_text())
    assert state == {"abcdef123456": tp.stat().st_mtime}


def test_rerun_is_incremental(env):
    vault, tp = env
    cto.main()
    state1 = (vault / ".chat_import_state.json").read_text()
    note = next((vault / "chats" / "code").glob("*.md"))
    note_mtime = note.stat().st_mtime

    cto.main()  # nothing changed -> no rewrite, same state

    assert (vault / ".chat_import_state.json").read_text() == state1
    assert note.stat().st_mtime == note_mtime
    assert len(list((vault / "chats" / "code").glob("*.md"))) == 1


def test_changed_transcript_is_reimported(env):
    vault, tp = env
    cto.main()
    tp.write_text(transcript_lines(), encoding="utf-8")
    os.utime(tp, (tp.stat().st_mtime + 100, tp.stat().st_mtime + 100))
    cto.main()
    state = json.loads((vault / ".chat_import_state.json").read_text())
    assert state["abcdef123456"] == tp.stat().st_mtime


def test_state_write_is_atomic_on_replace_failure(env, monkeypatch):
    """If the final rename fails mid-import, the previous state file must remain a
    complete, valid JSON — never a partial write (that would force a full re-import
    or, worse, silently lose the incremental history)."""
    vault, tp = env
    prior = {"prior-session": 123.0}
    (vault / ".chat_import_state.json").write_text(json.dumps(prior))

    def boom(src, dst):
        raise OSError("simulated crash between tmp write and rename")
    monkeypatch.setattr(cto.os, "replace", boom)

    with pytest.raises(OSError):
        cto.main()

    # the state file was untouched by the failed run
    assert json.loads((vault / ".chat_import_state.json").read_text()) == prior
