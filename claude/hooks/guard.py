#!/usr/bin/env python3
"""guard.py — deterministic PreToolUse guard: your top lessons, compiled ($0, stdlib, <300ms).

Most recall fires happen at the risk gate, and the top-firing lessons tend to be
deploy/git safety rules — this hook promotes them from text hints to REAL guards:
permissionDecision deny/ask/warn with a distilled reason + fix. The semantic
risk-recall hook stays behind it as the long tail.

Rules are declarative in <PERSONAL_OS_HOME>/guards.json — probes are NAMED functions
in this file (never shell strings from JSON: no injection vector). Fail-open
everywhere: broken JSON / probe error / timeout => silent pass-through; work is
never blocked by the safety system itself.

Overrides: prefix the command with `POS_GUARD=skip ` => deny becomes ask (logged,
never a silent allow). Permanent: guards.json ("enabled": false, change the decision,
or "mode": "ask-only"). Every fire lands in the fire log
(type guard-deny|guard-ask|guard-warn) => visible in /os.

Config (env, all optional):
  PERSONAL_OS_HOME         guards.json + fire log location (default ~/.claude/personal-os)
  PERSONAL_OS_SCRIPTS_DIR  where pos_utils.py lives         (default ~/.personal-os/scripts)
"""
import json
import os
import re
import subprocess
import sys

GUARDS = os.path.join(os.path.expanduser(
    os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os")), "guards.json")

sys.path.insert(0, os.path.expanduser(
    os.environ.get("PERSONAL_OS_SCRIPTS_DIR", "~/.personal-os/scripts")))
try:
    import pos_utils
except Exception:
    pos_utils = None


def sh(cwd, *cmd, timeout=2):
    try:
        return subprocess.run(cmd, cwd=cwd or None, capture_output=True, text=True,
                              timeout=timeout).stdout
    except Exception:
        return ""


# ------------------------------------------------------------------- probes
# Each probe: (cwd, command, rule) -> bool | None. True = condition proven (rule
# fires), False = proven not, None = undeterminable (rule stays quiet). `rule` is
# the rule's own JSON dict, for per-rule config like "author_email".

def probe_env_without_vercelignore(cwd, _cmd, _rule):
    envs = [f for f in os.listdir(cwd or ".")
            if f.startswith(".env") and f != ".env.example"] if os.path.isdir(cwd or ".") else []
    if not envs:
        return False
    vi = os.path.join(cwd or ".", ".vercelignore")
    if not os.path.exists(vi):
        return True
    try:
        rules = open(vi, encoding="utf-8", errors="replace").read().splitlines()
    except Exception:
        return None
    return not any(r.strip().startswith(".env") for r in rules)


def probe_wrong_author(cwd, _cmd, rule):
    expected = (rule.get("author_email") or "").strip()
    if not expected:
        return None  # not configured -> never fire (set it in guards.json / installer)
    linked = os.path.isdir(os.path.join(cwd or ".", ".vercel")) or \
        os.path.exists(os.path.join(cwd or ".", "vercel.json"))
    if not linked:
        return False
    email = sh(cwd, "git", "config", "user.email").strip()
    if not email:
        return None
    return email != expected


def probe_behind_origin(cwd, _cmd, _rule):
    head = sh(cwd, "git", "rev-parse", "--abbrev-ref", "HEAD").strip()
    if not head or head == "HEAD":
        return None
    out = sh(cwd, "git", "rev-list", "--left-right", "--count",
             f"HEAD...origin/{head}").split()
    if len(out) != 2:
        return None
    return int(out[1]) > 0


def probe_preflight_stale(cwd, _cmd, _rule):
    gitdir = sh(cwd, "git", "rev-parse", "--git-dir").strip()
    if not gitdir:
        return None
    marker = os.path.join(cwd or ".", gitdir, "pos-preflight-ok")
    # only relevant in TypeScript projects
    if not os.path.exists(os.path.join(cwd or ".", "tsconfig.json")):
        return False
    if not os.path.exists(marker):
        return True
    try:
        import time
        content = open(marker, encoding="utf-8").read().strip()
        head = sh(cwd, "git", "rev-parse", "HEAD").strip()
        if content.split()[0] != head:
            return True
        return (time.time() - os.path.getmtime(marker)) > 30 * 60
    except Exception:
        return None


def probe_multi_worktree(cwd, _cmd, _rule):
    out = sh(cwd, "git", "worktree", "list", "--porcelain")
    if not out:
        return None
    return out.count("worktree ") > 1


def probe_index_prestaged(cwd, _cmd, _rule):
    return bool(sh(cwd, "git", "diff", "--cached", "--name-only").strip())


def probe_dirty_tracked(cwd, _cmd, _rule):
    out = sh(cwd, "git", "status", "--porcelain")
    if out == "":
        return False
    return any(l and not l.startswith("??") for l in out.splitlines())


PROBES = {
    "env_without_vercelignore": probe_env_without_vercelignore,
    "wrong_author": probe_wrong_author,
    "behind_origin": probe_behind_origin,
    "preflight_stale": probe_preflight_stale,
    "multi_worktree": probe_multi_worktree,
    "index_prestaged": probe_index_prestaged,
    "dirty_tracked": probe_dirty_tracked,
    "always": lambda cwd, cmd, rule: True,
}


def fire_log(rec):
    if pos_utils:
        pos_utils.fire_log_append(rec)


def emit(decision, reason):
    if decision == "warn":
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse", "additionalContext": reason}}))
    else:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason}}))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    tool = data.get("tool_name") or ""
    if "Bash" not in tool and tool:
        return
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd:
        return
    cwd = data.get("cwd") or os.getcwd()

    override = cmd.lstrip().startswith("POS_GUARD=skip")
    try:
        cfg = json.load(open(GUARDS, encoding="utf-8"))
    except Exception:
        return  # fail-open: a broken/missing config never blocks
    mode = cfg.get("mode", "ask-only")

    for rule in cfg.get("rules", []):
        if not rule.get("enabled", True):
            continue
        try:
            if not re.search(rule.get("matcher", "$^"), cmd, re.I):
                continue
            results = []
            for pname in rule.get("probes", ["always"]):
                fn = PROBES.get(pname)
                results.append(fn(cwd, cmd, rule) if fn else None)
            if not any(r is True for r in results):
                continue  # condition not proven -> the rule does not fire
        except Exception:
            continue  # probe error -> fail-open
        decision = rule.get("decision", "warn")
        if decision == "deny" and (override or mode == "ask-only"):
            decision = "ask"
        reason = rule.get("reason", "") + f"  {rule.get('lesson', '')}" \
            + ("  (POS_GUARD=skip active)" if override else
               ("  (skip: prefix the command with `POS_GUARD=skip `)"
                if rule.get("decision") == "deny" else ""))
        fire_log({"type": f"guard-{decision}", "rule": rule.get("id"),
                  "path": rule.get("lesson", "").strip("[]"),
                  "trigger": "PreToolUse:guard", "prompt": cmd[:80],
                  "override": override})
        emit(decision, reason.strip())
        return  # first matching rule wins — exactly ONE decision per command


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
