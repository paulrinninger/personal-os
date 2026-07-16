"""pos_health — begin/step/finalize merge, ok computation, notification debounce,
and `check` exit codes. subprocess.run (the notifier) is mocked throughout."""
import datetime as dt
import json

import pytest

import pos_utils
import pos_health


@pytest.fixture
def health_home(tmp_path, monkeypatch):
    po = tmp_path / "personal-os"
    monkeypatch.setattr(pos_utils, "PO", str(po))
    monkeypatch.setattr(pos_utils, "LOCK_ROOT", str(po / "locks"))
    monkeypatch.setattr(pos_health, "PO", str(po))
    monkeypatch.setattr(pos_health, "HEALTH", str(po / "health.json"))
    monkeypatch.setattr(pos_health, "STEPS_DIR", str(po / "health"))
    return po


@pytest.fixture
def notifications(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)

        class P:
            returncode = 0
        return P()
    monkeypatch.setattr(pos_health.subprocess, "run", fake_run)
    return calls


def load_health(po):
    return json.load(open(po / "health.json", encoding="utf-8"))


def test_begin_step_finalize_green(health_home, notifications):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "qmd update", "0", "12.7")
    pos_health.cmd_step("graph", "vault autopush", "0", "3")
    pos_health.cmd_finalize("graph")

    d = load_health(health_home)
    job = d["jobs"]["graph"]
    assert job["ok"] is True
    assert [s["name"] for s in job["steps"]] == ["qmd update", "vault autopush"]
    assert job["steps"][0]["secs"] == 12            # float secs coerced to int
    assert job["start"] and job["end"]
    assert notifications == []                      # green run -> no notification


def test_begin_resets_previous_steps(health_home, notifications):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "old step", "1", "1")
    pos_health.cmd_begin("graph")                   # a new run starts fresh
    pos_health.cmd_step("graph", "new step", "0", "1")
    pos_health.cmd_finalize("graph")
    job = load_health(health_home)["jobs"]["graph"]
    assert [s["name"] for s in job["steps"]] == ["new step"]
    assert job["ok"] is True


def test_failed_step_marks_job_and_notifies_once(health_home, notifications):
    pos_health.cmd_begin("dream")
    pos_health.cmd_step("dream", "residue", "124", "900")
    pos_health.cmd_finalize("dream")

    d = load_health(health_home)
    assert d["jobs"]["dream"]["ok"] is False
    assert len(notifications) == 1
    assert d["notified"]["date"] == dt.date.today().isoformat()


def test_notify_debounce_once_per_day(health_home, notifications):
    for _ in range(3):
        pos_health.cmd_begin("dream")
        pos_health.cmd_step("dream", "residue", "1", "5")
        pos_health.cmd_finalize("dream")
    assert len(notifications) == 1                  # 3 degraded runs, 1 notification


def test_no_steps_means_not_ok(health_home, notifications):
    pos_health.cmd_begin("graph")
    pos_health.cmd_finalize("graph")                # begin marker only, zero steps
    assert load_health(health_home)["jobs"]["graph"]["ok"] is False


def test_doctor_record_fail_notifies(health_home, notifications):
    pos_health.cmd_doctor_record("FAIL", "2", "1", "10")
    d = load_health(health_home)
    assert d["doctor"]["verdict"] == "FAIL" and d["doctor"]["fail"] == 2
    assert len(notifications) == 1
    pos_health.cmd_doctor_record("OK", "0", "0", "13")
    assert load_health(health_home)["doctor"]["verdict"] == "OK"
    assert len(notifications) == 1                  # OK never notifies


# ------------------------------------------------------------------- check

def test_check_green(health_home, notifications, capsys):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "a", "0", "1")
    pos_health.cmd_finalize("graph")
    assert pos_health.cmd_check() == 0
    assert capsys.readouterr().out.startswith("OK")


def test_check_no_data_is_degraded(health_home, capsys):
    assert pos_health.cmd_check() == 1
    assert "DEGRADED" in capsys.readouterr().out


def test_check_failed_job_is_degraded(health_home, notifications, capsys):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "qmd", "2", "1")
    pos_health.cmd_finalize("graph")
    assert pos_health.cmd_check() == 1
    assert "qmd" in capsys.readouterr().out


def test_check_stale_run_is_degraded(health_home, notifications, capsys):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "a", "0", "1")
    pos_health.cmd_finalize("graph")
    # age the run beyond STALE_HOURS
    d = load_health(health_home)
    old = (dt.datetime.now() - dt.timedelta(hours=40)).isoformat(timespec="seconds")
    d["jobs"]["graph"]["end"] = old
    pos_utils.write_atomic(str(health_home / "health.json"), d)
    assert pos_health.cmd_check() == 1
    assert "no nightly run" in capsys.readouterr().out


def test_check_doctor_fail_is_degraded(health_home, notifications, capsys):
    pos_health.cmd_begin("graph")
    pos_health.cmd_step("graph", "a", "0", "1")
    pos_health.cmd_finalize("graph")
    pos_health.cmd_doctor_record("FAIL", "1", "0", "5")
    assert pos_health.cmd_check() == 1
    assert "doctor FAIL" in capsys.readouterr().out
