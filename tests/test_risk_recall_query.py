"""risk-recall searches for the risky ACTION, not for the content of its arguments."""
import importlib.util
import os

HOOK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "claude", "hooks", "risk-recall.py")


def _hook():
    spec = importlib.util.spec_from_file_location("risk_recall_under_test", HOOK)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_commit_message_is_not_the_query():
    rr = _hook()
    q, label = rr.extract_query({"tool_name": "Bash", "tool_input": {
        "command": 'git add -- a.py && git commit -m "Nightly thinker: transport errors burn jobs"'}})
    assert label == "Bash"
    assert "git commit -m" in q
    assert "transport" not in q and "Nightly" not in q


def test_heredoc_body_is_not_the_query():
    rr = _hook()
    cmd = "git commit -F - <<'EOF'\nlong message about ollama and backups\nEOF"
    q, _ = rr.extract_query({"tool_name": "Bash", "tool_input": {"command": cmd}})
    assert "ollama" not in q and "backups" not in q
    assert q.startswith("git commit -F -")


def test_quoted_command_after_sh_c_stays():
    rr = _hook()
    q, _ = rr.extract_query({"tool_name": "Bash", "tool_input": {
        "command": 'ssh prod "git push origin main"'}})
    assert "git push origin main" in q


def test_non_risky_command_yields_no_query():
    rr = _hook()
    assert rr.extract_query({"tool_name": "Bash", "tool_input": {"command": "ls -la"}}) == (None, None)
