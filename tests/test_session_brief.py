"""session-brief.py — the SessionStart project brief: hub-path match, slug fallback,
un-hubbed log fallback, silence in throwaway cwds, stale-skip, and the 25-line cap."""
import importlib.util
import io
import json
import os
import time

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SB_PY = os.path.join(REPO, "claude", "hooks", "session-brief.py")

spec = importlib.util.spec_from_file_location("session_brief", SB_PY)
sb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sb)


class _QmdStub:
    """qmd_search stand-in — no qmd binary in CI."""

    def __init__(self, outcome="no_qmd", hits=None):
        self.outcome = outcome
        self.hits = hits or []

    def vsearch(self, query, n=5, timeout=45):
        return {"outcome": self.outcome, "hits": self.hits, "error": ""}


@pytest.fixture
def brief_env(tmp_path, monkeypatch, po_home):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    (vault / "logs").mkdir()
    monkeypatch.setattr(sb, "VAULT", str(vault))
    monkeypatch.setattr(sb, "qmd_search", _QmdStub())
    return vault


def run_brief(monkeypatch, capsys, cwd):
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps({"cwd": str(cwd)})))
    capsys.readouterr()
    sb.main()
    out = capsys.readouterr().out.strip()
    if not out:
        return None
    return json.loads(out)["hookSpecificOutput"]["additionalContext"]


def _hub(vault, name, path=None, stand="Building the parser — v2 shipping"):
    extra = f"path: {path}\n" if path else ""
    (vault / "projects" / f"{name}.md").write_text(
        f"---\ntitle: {name}\nstatus: active\n{extra}---\n\n"
        f"**What:** a thing\n**Stand (2026-07-01) / Status:** {stand}\n\n## Offen / Open\n- x\n")


def _log(vault, name, bullets=("- finish tests", "- ship v0.4"), age_days=1):
    p = vault / "logs" / name
    p.write_text("---\ntitle: log\n---\n\n## Was lief / What happened\n- stuff\n\n"
                 "## Offen / Pending\n" + "\n".join(bullets) + "\n")
    t = time.time() - age_days * 86400
    os.utime(p, (t, t))
    return p


def test_hub_path_match_wins(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "code" / "some-checkout-dir"
    cwd.mkdir(parents=True)
    _hub(brief_env, "myproj", path=str(cwd))
    _hub(brief_env, "somecheckoutdir")  # slug-similar decoy — path match must win
    out = run_brief(monkeypatch, capsys, cwd)
    assert out.startswith("PROJECT BRIEF myproj")
    assert "Building the parser" in out


def test_slug_fallback(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "my-app"
    cwd.mkdir()
    _hub(brief_env, "myapp")  # no path: frontmatter -> slug match on the basename
    out = run_brief(monkeypatch, capsys, cwd)
    assert out.startswith("PROJECT BRIEF myapp")


def test_unhubbed_log_fallback_shows_open_items(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "sidequest"
    cwd.mkdir()
    _hub(brief_env, "unrelated-project")
    _log(brief_env, "2026-07-18-sidequest-session.md")
    out = run_brief(monkeypatch, capsys, cwd)
    assert "PROJECT BRIEF sidequest" in out
    assert "- finish tests" in out


def test_tmp_and_home_cwd_stay_silent(brief_env, monkeypatch, capsys):
    _hub(brief_env, "tmp")  # even a matching hub must not fire in throwaway cwds
    assert run_brief(monkeypatch, capsys, "/tmp") is None
    assert run_brief(monkeypatch, capsys, "/private/tmp") is None
    assert run_brief(monkeypatch, capsys, os.path.expanduser("~")) is None


def test_no_hub_no_log_is_silent(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "unknown-project"
    cwd.mkdir()
    assert run_brief(monkeypatch, capsys, cwd) is None


def test_stale_log_only_is_silent(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "oldthing"
    cwd.mkdir()
    _log(brief_env, "2026-01-01-oldthing-session.md", age_days=30)  # > STALE_DAYS
    assert run_brief(monkeypatch, capsys, cwd) is None


def test_qmd_lessons_line_and_miss_logging(brief_env, monkeypatch, capsys, tmp_path):
    import pos_utils
    cwd = tmp_path / "withhub"
    cwd.mkdir()
    _hub(brief_env, "withhub", path=str(cwd))
    monkeypatch.setattr(sb, "qmd_search", _QmdStub(outcome="ok", hits=[
        {"path": "lessons/always-fetch-first.md", "score": 88},
        {"path": "knowledge/other.md", "score": 80},
    ]))
    out = run_brief(monkeypatch, capsys, cwd)
    assert "Relevant lessons:" in out
    assert "lessons/always-fetch-first.md (88%)" in out
    assert "knowledge/other.md" not in out  # lessons/ hits only
    # a qmd miss is fire-logged, not shown
    monkeypatch.setattr(sb, "qmd_search", _QmdStub(outcome="timeout"))
    out = run_brief(monkeypatch, capsys, cwd)
    assert "Relevant lessons" not in out
    rows = [json.loads(l) for l in open(pos_utils.FIRE_LOG, encoding="utf-8")]
    assert rows[-1]["type"] == "timeout" and rows[-1]["trigger"] == "SessionStart"


def test_output_capped_at_25_lines(brief_env, monkeypatch, capsys, tmp_path):
    cwd = tmp_path / "bigproj"
    cwd.mkdir()
    _hub(brief_env, "bigproj", path=str(cwd), stand="x " * 300)
    _log(brief_env, "2026-07-18-bigproj-session.md",
         bullets=tuple(f"- item {i}" for i in range(20)))
    out = run_brief(monkeypatch, capsys, cwd)
    assert len(out.splitlines()) <= 25
    # the open-items list itself is capped at 6 bullets
    assert sum(1 for l in out.splitlines() if l.strip().startswith("- item")) <= 6