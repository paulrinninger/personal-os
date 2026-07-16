"""Fire-log: append (ts + type carried), compact (age rotation, keeps unparseable),
and os_lessons.load_fires ignoring miss records."""
import datetime as dt
import json
import os

import pos_utils
import os_lessons


def read_lines(path):
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


# ----------------------------------------------------------------------- append

def test_append_adds_ts_and_keeps_type(po_home):
    log = str(po_home / "lesson-fires.jsonl")
    pos_utils.fire_log_append({"type": "hit", "path": "lessons/x.md", "score": 70},
                              fire_log=log)
    pos_utils.fire_log_append({"type": "zero", "trigger": "UserPromptSubmit"},
                              fire_log=log)
    recs = read_lines(log)
    assert len(recs) == 2
    assert all("ts" in r for r in recs)
    dt.datetime.fromisoformat(recs[0]["ts"])          # parseable timestamp
    assert recs[0]["type"] == "hit" and recs[1]["type"] == "zero"


def test_append_respects_existing_ts(po_home):
    log = str(po_home / "lesson-fires.jsonl")
    pos_utils.fire_log_append({"type": "hit", "ts": "2020-01-01T00:00:00"}, fire_log=log)
    assert read_lines(log)[0]["ts"] == "2020-01-01T00:00:00"


def test_append_never_raises(tmp_path):
    # unwritable target directory -> silently dropped (fail-open)
    pos_utils.fire_log_append({"type": "hit"}, fire_log="/dev/null/nope/x.jsonl")


# ---------------------------------------------------------------------- compact

def test_compact_drops_old_keeps_recent_and_unparseable(po_home):
    log = str(po_home / "lesson-fires.jsonl")
    old_ts = (dt.datetime.now() - dt.timedelta(days=200)).isoformat(timespec="seconds")
    new_ts = (dt.datetime.now() - dt.timedelta(days=2)).isoformat(timespec="seconds")
    os.makedirs(po_home, exist_ok=True)
    with open(log, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": old_ts, "type": "hit", "path": "a"}) + "\n")
        f.write(json.dumps({"ts": new_ts, "type": "hit", "path": "b"}) + "\n")
        f.write("not json at all\n")
        f.write(json.dumps({"type": "hit", "path": "no-ts"}) + "\n")

    dropped = pos_utils.fire_log_compact(days=180, fire_log=log)

    assert dropped == 1
    kept = open(log, encoding="utf-8").read().splitlines()
    assert len(kept) == 3
    assert "not json at all" in kept          # unparseable kept (caution over eagerness)
    assert not any('"a"' in l for l in kept)  # the 200-day-old line is gone


def test_compact_missing_file_is_zero(po_home):
    assert pos_utils.fire_log_compact(days=180, fire_log=str(po_home / "nope.jsonl")) == 0


def test_compact_noop_when_nothing_old(po_home):
    log = str(po_home / "lesson-fires.jsonl")
    pos_utils.fire_log_append({"type": "hit", "path": "x"}, fire_log=log)
    before = open(log).read()
    assert pos_utils.fire_log_compact(days=180, fire_log=log) == 0
    assert open(log).read() == before


# ---------------------------------------------------- os_lessons.load_fires

def test_load_fires_ignores_miss_records(tmp_path, monkeypatch):
    log = tmp_path / "lesson-fires.jsonl"
    now = dt.datetime.now().isoformat(timespec="seconds")
    with open(log, "w", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now, "type": "hit", "path": "lessons/a.md", "score": 70}) + "\n")
        f.write(json.dumps({"ts": now, "type": "zero", "path": "lessons/a.md"}) + "\n")
        f.write(json.dumps({"ts": now, "type": "timeout", "path": "lessons/b.md"}) + "\n")
        f.write(json.dumps({"ts": now, "path": "lessons/c.md", "score": 60}) + "\n")  # legacy: no type -> hit
    monkeypatch.setattr(os_lessons, "FIRE_LOG", str(log))

    agg = os_lessons.load_fires()

    assert agg["lessons/a.md"]["count"] == 1     # the zero record did NOT count
    assert "lessons/b.md" not in agg             # timeout-only path absent
    assert agg["lessons/c.md"]["count"] == 1     # pre-0.3 records still count as hits
