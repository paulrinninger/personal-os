"""guard.py — the deterministic PreToolUse guard: exact decisions against real
fixture git repos, ask-only downgrade, POS_GUARD=skip, fail-open on a broken
config, and the hard PII invariant on guards.example.json."""
import importlib.util
import io
import json
import os
import subprocess

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD_PY = os.path.join(REPO, "claude", "hooks", "guard.py")
EXAMPLE = os.path.join(REPO, "claude", "personal-os", "guards.example.json")

spec = importlib.util.spec_from_file_location("guard", GUARD_PY)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def _git(cwd, *args):
    subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                   check=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init")
    _git(r, "config", "user.email", "someone@example.com")
    _git(r, "config", "user.name", "Someone")
    (r / "f.txt").write_text("hello\n")
    _git(r, "add", "f.txt")
    _git(r, "commit", "-m", "init")
    return r


def run_guard(monkeypatch, capsys, tmp_path, cfg, cmd, cwd):
    gpath = tmp_path / "guards.json"
    gpath.write_text(cfg if isinstance(cfg, str) else json.dumps(cfg))
    monkeypatch.setattr(guard, "GUARDS", str(gpath))
    payload = {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(cwd)}
    monkeypatch.setattr("sys.stdin", io.StringIO(json.dumps(payload)))
    capsys.readouterr()
    guard.main()
    out = capsys.readouterr().out.strip()
    return json.loads(out)["hookSpecificOutput"] if out else None


def _rule(**kw):
    base = {"id": "r", "enabled": True, "matcher": "$^", "probes": ["always"],
            "decision": "deny", "reason": "reason text", "lesson": "[[some-lesson]]"}
    base.update(kw)
    return base


STAGE_RULE = _rule(id="stage-all-shared-tree",
                   matcher=r"git\s+add\s+(-A\b|--all\b|\.(\s|$|;))",
                   probes=["multi_worktree"],
                   reason="multiple worktrees: git add -A sweeps foreign WIP")
RESET_RULE = _rule(id="reset-hard-wip", matcher=r"git\s+reset\s+--hard",
                   probes=["dirty_tracked"], decision="ask",
                   reason="tracked WIP uncommitted")
ENV_RULE = _rule(id="vercelignore-env", matcher=r"vercel\s+(deploy\b|--prod)",
                 probes=["env_without_vercelignore"],
                 reason=".env without .vercelignore")
AUTHOR_RULE = _rule(id="deploy-wrong-author", matcher=r"git\s+push|vercel\s+--prod",
                    probes=["wrong_author"], author_email="owner@example.com",
                    reason="wrong git author")


def cfg(mode, *rules):
    return {"version": 1, "mode": mode, "rules": list(rules)}


# ----------------------------------------------------------- fixture repos
def test_multi_worktree_stage_all_denies(repo, monkeypatch, capsys, tmp_path, po_home):
    _git(repo, "worktree", "add", str(tmp_path / "wt"), "-b", "wt-branch")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", STAGE_RULE),
                    "git add -A", repo)
    assert out["permissionDecision"] == "deny"
    assert "worktrees" in out["permissionDecisionReason"]
    assert "[[some-lesson]]" in out["permissionDecisionReason"]


def test_single_worktree_stage_all_is_silent(repo, monkeypatch, capsys, tmp_path, po_home):
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", STAGE_RULE),
                    "git add -A", repo)
    assert out is None  # probe proven False -> rule does not fire


def test_dirty_tracked_reset_hard_asks(repo, monkeypatch, capsys, tmp_path, po_home):
    (repo / "f.txt").write_text("modified\n")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", RESET_RULE),
                    "git reset --hard HEAD", repo)
    assert out["permissionDecision"] == "ask"


def test_clean_tree_reset_hard_is_silent(repo, monkeypatch, capsys, tmp_path, po_home):
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", RESET_RULE),
                    "git reset --hard HEAD", repo)
    assert out is None


def test_env_without_vercelignore_denies(repo, monkeypatch, capsys, tmp_path, po_home):
    (repo / ".env").write_text("SECRET=x\n")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", ENV_RULE),
                    "vercel deploy --prod", repo)
    assert out["permissionDecision"] == "deny"


def test_env_covered_by_vercelignore_is_silent(repo, monkeypatch, capsys, tmp_path, po_home):
    (repo / ".env").write_text("SECRET=x\n")
    (repo / ".vercelignore").write_text(".env\n.env.*\n")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", ENV_RULE),
                    "vercel deploy --prod", repo)
    assert out is None


def test_wrong_author_via_local_config_denies(repo, monkeypatch, capsys, tmp_path, po_home):
    (repo / "vercel.json").write_text("{}\n")  # deploy-linked project
    # repo-local user.email is someone@example.com, rule expects owner@example.com
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", AUTHOR_RULE),
                    "git push origin main", repo)
    assert out["permissionDecision"] == "deny"


def test_unconfigured_author_email_keeps_rule_dormant(repo, monkeypatch, capsys,
                                                      tmp_path, po_home):
    (repo / "vercel.json").write_text("{}\n")
    rule = dict(AUTHOR_RULE, author_email="")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", rule),
                    "git push origin main", repo)
    assert out is None  # probe returns None -> never fires


def test_preflight_rule_ignores_non_ts_projects(repo, monkeypatch, capsys, tmp_path,
                                                po_home):
    rule = _rule(id="deploy-no-preflight", matcher=r"git\s+push",
                 probes=["preflight_stale"], decision="ask", reason="no preflight")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", rule),
                    "git push", repo)
    assert out is None  # no tsconfig.json -> probe False


# ------------------------------------------------- modes, override, fail-open
def test_ask_only_mode_downgrades_deny(repo, monkeypatch, capsys, tmp_path, po_home):
    _git(repo, "worktree", "add", str(tmp_path / "wt2"), "-b", "wt-branch-2")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("ask-only", STAGE_RULE),
                    "git add -A", repo)
    assert out["permissionDecision"] == "ask"


def test_pos_guard_skip_downgrades_and_is_labelled(repo, monkeypatch, capsys,
                                                   tmp_path, po_home):
    _git(repo, "worktree", "add", str(tmp_path / "wt3"), "-b", "wt-branch-3")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", STAGE_RULE),
                    "POS_GUARD=skip git add -A", repo)
    assert out["permissionDecision"] == "ask"  # never a silent allow
    assert "POS_GUARD=skip active" in out["permissionDecisionReason"]


def test_broken_guards_json_fails_open(repo, monkeypatch, capsys, tmp_path, po_home):
    out = run_guard(monkeypatch, capsys, tmp_path, "{ this is not json",
                    "git add -A", repo)
    assert out is None


def test_warn_emits_context_not_decision(repo, monkeypatch, capsys, tmp_path, po_home):
    rule = _rule(id="verify-contract", matcher=r"vercel\s+--prod",
                 probes=["always"], decision="warn", reason="verify after deploy")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", rule),
                    "vercel --prod", repo)
    assert "permissionDecision" not in out
    assert "verify after deploy" in out["additionalContext"]


def test_first_matching_rule_wins(repo, monkeypatch, capsys, tmp_path, po_home):
    first = _rule(id="first", matcher=r"vercel", probes=["always"],
                  decision="ask", reason="FIRST")
    second = _rule(id="second", matcher=r"vercel", probes=["always"],
                   decision="deny", reason="SECOND")
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", first, second),
                    "vercel deploy", repo)
    assert out["permissionDecision"] == "ask"
    assert "FIRST" in out["permissionDecisionReason"]


def test_disabled_rule_never_fires(repo, monkeypatch, capsys, tmp_path, po_home):
    rule = _rule(id="off", matcher=r"vercel", probes=["always"], enabled=False)
    out = run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", rule),
                    "vercel deploy", repo)
    assert out is None


def test_fires_land_in_fire_log(repo, monkeypatch, capsys, tmp_path, po_home):
    import pos_utils
    _git(repo, "worktree", "add", str(tmp_path / "wt4"), "-b", "wt-branch-4")
    run_guard(monkeypatch, capsys, tmp_path, cfg("enforce", STAGE_RULE),
              "git add -A", repo)
    rows = [json.loads(l) for l in open(pos_utils.FIRE_LOG, encoding="utf-8")]
    assert rows[-1]["type"] == "guard-deny"
    assert rows[-1]["rule"] == "stage-all-shared-tree"


# ------------------------------------------------------------ PII invariant
def test_guards_example_carries_no_personal_data():
    import re as _re
    text = open(EXAMPLE, encoding="utf-8").read()
    # no email address of any kind, no home-directory path, no personal launchd label
    assert _re.search(r"[\w.+-]+@[\w-]+\.[\w.]+", text) is None
    assert "/Users/" not in text and "/home/" not in text
    data = json.loads(text)
    rules_with_author = [r for r in data["rules"] if "author_email" in r]
    assert rules_with_author, "the wrong-author rule must ship (with a placeholder)"
    for rule in rules_with_author:
        assert rule["author_email"] == ""  # placeholder, filled by the installer
