"""pos_actions.py — journal + undo: every op must roundtrip byte-identical, every
precondition-miss must skip (never clobber the user's own edits), and every undo
must land as `rejected` feedback."""
import datetime as dt
import json
import os
from types import SimpleNamespace

import pos_actions


def _args(**kw):
    base = dict(last=None, night=None, id=None, dry_run=False, action=None)
    base.update(kw)
    return SimpleNamespace(**base)


def _read(path):
    return open(path, encoding="utf-8").read()


def _journal_rows():
    return pos_actions._read_journal()


NIGHT = dt.date.today().isoformat()


# --------------------------------------------------------------- roundtrips
def test_remove_lines_roundtrip_byte_identical(autopilot_env):
    a = autopilot_env.vault / "lessons" / "a.md"
    b = autopilot_env.vault / "lessons" / "b.md"
    a.parent.mkdir(parents=True)
    orig_a = "# A\n\nbody\n\n## Links\n- [[old]]\n"
    orig_b = "# B\n\nbody\n"
    a.write_text(orig_a)
    b.write_text(orig_b)
    la, lb = "- [[b]] — auto-link", "- [[a]] — auto-link"
    a.write_text(orig_a + la + "\n")
    b.write_text(orig_b + lb + "\n")
    pos_actions.journal({"action": "link.add", "night": NIGHT,
                         "targets": [str(a), str(b)],
                         "evidence": {"pass": "connections", "score": 90},
                         "undo": {"op": "remove_lines",
                                  "items": [{"path": str(a), "line": la},
                                            {"path": str(b), "line": lb}]}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(a)) == orig_a
    assert _read(str(b)) == orig_b


def test_move_roundtrip_byte_identical(autopilot_env):
    src = autopilot_env.vault / "_inbox" / "refs" / "card.md"
    dst = autopilot_env.vault / "_inbox" / "refs" / "_archive" / "card.md"
    dst.parent.mkdir(parents=True)
    content = "---\nstatus: inbox\n---\n\ncard body\n"
    src.write_text(content)
    os.rename(src, dst)
    pos_actions.journal({"action": "card.archive", "night": NIGHT, "targets": [str(src)],
                         "undo": {"op": "move", "from": str(src), "to": str(dst)}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert src.exists() and not dst.exists()
    assert _read(str(src)) == content


def test_set_status_roundtrip_byte_identical(autopilot_env):
    f = autopilot_env.vault / "_inbox" / "dreams" / "2026-01-01-dream.md"
    f.parent.mkdir(parents=True)
    orig = "---\ntitle: Dream\nstatus: draft\ntype: dream\n---\n\nbody\n"
    f.write_text(orig)
    f.write_text(orig.replace("status: draft", "status: superseded", 1))
    pos_actions.journal({"action": "note.status", "night": NIGHT, "targets": [str(f)],
                         "undo": {"op": "set_status", "path": str(f),
                                  "old": "draft", "new": "superseded"}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(f)) == orig


def test_remove_state_line_roundtrip_byte_identical(autopilot_env):
    state = autopilot_env.vault / ".chat_mining_state.txt"
    orig = "one.md\ntwo.md\n"
    state.write_text(orig + "three.md\n")
    pos_actions.journal({"action": "state.advance", "night": NIGHT, "targets": ["three.md"],
                         "undo": {"op": "remove_state_line", "path": str(state),
                                  "line": "three.md"}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(state)) == orig


def test_requeue_roundtrip_byte_identical(autopilot_env, tmp_path):
    queue = tmp_path / "personal-os" / "harvest-queue.jsonl"
    done = tmp_path / "personal-os" / "harvest-queue-done.jsonl"
    queue.parent.mkdir(parents=True, exist_ok=True)
    entry = {"session_id": "s1", "transcript_path": "/x/t.jsonl", "cwd": "/x"}
    line = json.dumps(entry, ensure_ascii=False)
    orig = line + "\n"
    queue.write_text(orig)
    # simulate the drain: queue emptied, done row appended
    queue.write_text("")
    done.write_text(json.dumps({**entry, "done_ts": "t", "reason": "drafted"}) + "\n")
    pos_actions.journal({"action": "queue.done", "night": NIGHT, "targets": ["s1"],
                         "evidence": {"pass": "harvest", "reason": "drafted"},
                         "undo": {"op": "requeue", "queue": str(queue),
                                  "done": str(done), "line": line}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(queue)) == orig
    assert _read(str(done)) == ""  # the done row is gone


# --------------------------------------------------- preconditions -> skip
def test_remove_lines_skips_when_user_already_removed(autopilot_env):
    f = autopilot_env.vault / "n.md"
    f.write_text("# N\n")  # the auto-link is already gone
    pos_actions.journal({"action": "link.add", "night": NIGHT, "targets": [str(f)],
                         "undo": {"op": "remove_lines",
                                  "items": [{"path": str(f), "line": "- [[x]]"}]}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    rows = _journal_rows()
    assert any(r["action"] == "undo.skipped" and "lines-already-gone" in r["reason"]
               for r in rows)
    assert not any(r["action"] == "undo" for r in rows)
    assert _read(str(f)) == "# N\n"  # untouched


def test_move_skips_when_original_path_occupied(autopilot_env):
    src = autopilot_env.vault / "card.md"
    dst = autopilot_env.vault / "archived-card.md"
    dst.write_text("archived\n")
    src.write_text("the user recreated this file\n")
    pos_actions.journal({"action": "card.archive", "night": NIGHT, "targets": [str(src)],
                         "undo": {"op": "move", "from": str(src), "to": str(dst)}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(src)) == "the user recreated this file\n"
    assert any(r["action"] == "undo.skipped" and "occupied" in r["reason"]
               for r in _journal_rows())


def test_set_status_skips_when_user_changed_it(autopilot_env):
    f = autopilot_env.vault / "note.md"
    f.write_text("---\nstatus: reviewed\n---\n")  # user moved it on already
    pos_actions.journal({"action": "note.status", "night": NIGHT, "targets": [str(f)],
                         "undo": {"op": "set_status", "path": str(f),
                                  "old": "draft", "new": "superseded"}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(f)) == "---\nstatus: reviewed\n---\n"
    assert any(r["action"] == "undo.skipped" for r in _journal_rows())


def test_double_undo_is_a_noop(autopilot_env, capsys):
    f = autopilot_env.vault / "s.md"
    f.write_text("a\nx\n")
    pos_actions.journal({"action": "state.advance", "night": NIGHT, "targets": ["x"],
                         "undo": {"op": "remove_state_line", "path": str(f), "line": "x"}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert _read(str(f)) == "a\n"
    capsys.readouterr()
    pos_actions.cmd_undo(_args(night=NIGHT))  # the undone action is filtered out now
    assert "nothing to undo" in capsys.readouterr().out
    assert _read(str(f)) == "a\n"


def test_dry_run_changes_nothing(autopilot_env):
    f = autopilot_env.vault / "d.md"
    f.write_text("keep\nline\n")
    pos_actions.journal({"action": "state.advance", "night": NIGHT, "targets": ["line"],
                         "undo": {"op": "remove_state_line", "path": str(f), "line": "line"}})
    pos_actions.cmd_undo(_args(night=NIGHT, dry_run=True))
    assert _read(str(f)) == "keep\nline\n"
    assert not any(r["action"] in ("undo", "undo.skipped") for r in _journal_rows())


# ------------------------------------------------------- feedback channel
def test_undo_writes_rejected_feedback(autopilot_env):
    f = autopilot_env.vault / "fb.md"
    f.write_text("x\nauto\n")
    pos_actions.journal({"action": "link.add", "night": NIGHT, "targets": [str(f)],
                         "evidence": {"pass": "connections", "score": 88},
                         "undo": {"op": "remove_lines",
                                  "items": [{"path": str(f), "line": "auto"}]}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    rows = [json.loads(l) for l in open(pos_actions.FEEDBACK, encoding="utf-8")]
    assert rows and rows[-1]["verdict"] == "rejected" \
        and rows[-1]["pass"] == "connections"


def test_undo_without_pass_writes_no_feedback(autopilot_env):
    f = autopilot_env.vault / "nf.md"
    f.write_text("---\nstatus: superseded\n---\n")
    pos_actions.journal({"action": "note.status", "night": NIGHT, "targets": [str(f)],
                         "undo": {"op": "set_status", "path": str(f),
                                  "old": "draft", "new": "superseded"}})
    pos_actions.cmd_undo(_args(night=NIGHT))
    assert not os.path.exists(pos_actions.FEEDBACK)


# -------------------------------------------------- implicit feedback scan
def _aged_journal(autopilot_env, rec, days):
    ts = (dt.datetime.now() - dt.timedelta(days=days)).isoformat(timespec="seconds")
    pos_actions.journal({**rec, "ts": ts})


def test_collect_feedback_rejected_when_link_removed(autopilot_env):
    f = autopilot_env.vault / "l.md"
    f.write_text("body\n")  # link line NOT present anymore
    _aged_journal(autopilot_env,
                  {"action": "link.add", "night": "2026-01-01", "targets": [str(f)],
                   "evidence": {"pass": "connections"},
                   "undo": {"op": "remove_lines",
                            "items": [{"path": str(f), "line": "- [[x]] auto"}]}},
                  days=3)
    pos_actions.cmd_collect_feedback(None)
    rows = [json.loads(l) for l in open(pos_actions.FEEDBACK, encoding="utf-8")]
    assert rows[-1]["verdict"] == "rejected"


def test_collect_feedback_accepted_when_link_survived_two_weeks(autopilot_env):
    f = autopilot_env.vault / "l2.md"
    f.write_text("body\n- [[x]] auto\n")
    _aged_journal(autopilot_env,
                  {"action": "link.add", "night": "2026-01-01", "targets": [str(f)],
                   "evidence": {"pass": "connections"},
                   "undo": {"op": "remove_lines",
                            "items": [{"path": str(f), "line": "- [[x]] auto"}]}},
                  days=15)
    pos_actions.cmd_collect_feedback(None)
    rows = [json.loads(l) for l in open(pos_actions.FEEDBACK, encoding="utf-8")]
    assert rows[-1]["verdict"] == "accepted"


def test_collect_feedback_grace_window_and_sidecar(autopilot_env):
    f = autopilot_env.vault / "l3.md"
    f.write_text("body\n- [[x]] auto\n")
    # 1 day old -> inside the 48h grace window, no verdict yet
    _aged_journal(autopilot_env,
                  {"action": "link.add", "night": "2026-01-01", "targets": [str(f)],
                   "evidence": {"pass": "connections"},
                   "undo": {"op": "remove_lines",
                            "items": [{"path": str(f), "line": "- [[x]] auto"}]}},
                  days=1)
    pos_actions.cmd_collect_feedback(None)
    assert not os.path.exists(pos_actions.FEEDBACK)
    # a scored action is never scored twice (sidecar)
    f2 = autopilot_env.vault / "l4.md"
    f2.write_text("body\n")
    _aged_journal(autopilot_env,
                  {"action": "link.add", "night": "2026-01-02", "targets": [str(f2)],
                   "evidence": {"pass": "connections"},
                   "undo": {"op": "remove_lines",
                            "items": [{"path": str(f2), "line": "- gone"}]}},
                  days=3)
    pos_actions.cmd_collect_feedback(None)
    n1 = sum(1 for _ in open(pos_actions.FEEDBACK, encoding="utf-8"))
    pos_actions.cmd_collect_feedback(None)
    n2 = sum(1 for _ in open(pos_actions.FEEDBACK, encoding="utf-8"))
    assert n1 == n2 == 1
