"""qmd_search.py — the single shared qmd client (JSON mode). No qmd needed:
subprocess.run is mocked with canned output."""
import json
import subprocess

import pytest

import qmd_search


class FakeProc:
    def __init__(self, stdout):
        self.stdout = stdout


def with_stdout(payload):
    def _run(cmd, **kw):
        return FakeProc(payload)
    return _run


@pytest.fixture
def fake_qmd(monkeypatch):
    monkeypatch.setattr(qmd_search, "_qmd_bin", lambda: "/definitely/fake/qmd")


def test_hits_prefix_score_docid_and_abs_path(monkeypatch, tmp_path, fake_qmd):
    vault = tmp_path / "vault"
    (vault / "lessons").mkdir(parents=True)
    (vault / "lessons" / "foo.md").write_text("x", encoding="utf-8")
    monkeypatch.setattr(qmd_search, "VAULT", str(vault))
    payload = json.dumps([
        {"file": "qmd://lessons/foo.md", "score": 0.45, "docid": "#abc123",
         "line": 12, "title": "Foo",
         "snippet": "---\ntitle: Foo\n---\n- the actual content line"},
        {"file": "lessons/missing.md", "score": "not-a-number", "docid": None},
    ])
    monkeypatch.setattr(qmd_search.subprocess, "run", with_stdout(payload))

    res = qmd_search.vsearch("query")
    assert res["outcome"] == "ok" and res["error"] == ""
    h = res["hits"][0]
    assert h["path"] == "lessons/foo.md"                # qmd:// prefix stripped
    assert h["score"] == 45                             # 0.45 float -> 45 int
    assert h["docid"] == "abc123"                       # leading '#' stripped
    assert h["abs_path"] == str(vault / "lessons" / "foo.md")
    assert h["line"] == 12
    assert h["snippet"] == "- the actual content line"  # frontmatter skipped
    h2 = res["hits"][1]
    assert h2["path"] == "lessons/missing.md"           # no prefix -> kept as-is
    assert h2["score"] == 0                             # unparseable score -> 0
    assert h2["abs_path"] is None                       # file doesn't exist


def test_score_rounding(monkeypatch, fake_qmd):
    payload = json.dumps([{"file": "a.md", "score": 0.586}, {"file": "b.md", "score": 1.0}])
    monkeypatch.setattr(qmd_search.subprocess, "run", with_stdout(payload))
    res = qmd_search.vsearch("q")
    assert [h["score"] for h in res["hits"]] == [59, 100]


def test_malformed_stdout_is_error_not_crash(monkeypatch, fake_qmd):
    monkeypatch.setattr(qmd_search.subprocess, "run", with_stdout("this is { not json"))
    res = qmd_search.vsearch("q")
    assert res["outcome"] == "error"
    assert "bad json" in res["error"]
    assert res["hits"] == []


def test_empty_stdout_is_ok_with_no_hits(monkeypatch, fake_qmd):
    # empty output = qmd found nothing; that is a valid, non-error outcome
    monkeypatch.setattr(qmd_search.subprocess, "run", with_stdout(""))
    res = qmd_search.vsearch("q")
    assert res["outcome"] == "ok"
    assert res["hits"] == []


def test_non_list_json_yields_no_hits(monkeypatch, fake_qmd):
    monkeypatch.setattr(qmd_search.subprocess, "run", with_stdout('{"oops": 1}'))
    res = qmd_search.vsearch("q")
    assert res["outcome"] == "ok"
    assert res["hits"] == []


def test_timeout_outcome(monkeypatch, fake_qmd):
    def raise_timeout(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd="qmd", timeout=9)
    monkeypatch.setattr(qmd_search.subprocess, "run", raise_timeout)
    res = qmd_search.vsearch("q", timeout=9)
    assert res["outcome"] == "timeout"
    assert res["hits"] == []


def test_no_qmd_outcome(monkeypatch):
    monkeypatch.setattr(qmd_search, "_qmd_bin", lambda: None)
    res = qmd_search.vsearch("q")
    assert res["outcome"] == "no_qmd"
    assert res["hits"] == []


# ------------------------------------------------------------- snippet cleaner

def test_clean_snippet_skips_hunk_headers_and_short_lines():
    raw = "@@ -1,3 +1,3 @@\nshort\n- a real bullet line"
    assert qmd_search._clean_snippet(raw) == "- a real bullet line"


def test_clean_snippet_title_fallback_when_only_frontmatter():
    raw = '---\ntitle: "My Note Title"\ntags: [x]\nstatus: active\n---'
    assert qmd_search._clean_snippet(raw) == "My Note Title"


def test_clean_snippet_prefers_content_over_title():
    raw = "title: The Title\nThis is a long enough content sentence."
    assert qmd_search._clean_snippet(raw) == "This is a long enough content sentence."


def test_clean_snippet_empty():
    assert qmd_search._clean_snippet("") == ""
    assert qmd_search._clean_snippet(None) == ""
