#!/usr/bin/env python3
"""Personal OS doctor — check that everything is wired up. Read-only, $0.

Usage: python3 install/doctor.py [--vault-path ~/vault] [--claude-dir ~/.claude]
                                 [--scripts-dir ~/.personal-os/scripts]
"""
import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SMOKE_QUERY = "git push force overwrote a shared branch"
SMOKE_THRESHOLD = 58  # keep in sync with the recall hook


def expand(p):
    return os.path.abspath(os.path.expanduser(p))


def _import_qmd_search(scripts_dir):
    """Import the shared qmd client from the installed scripts dir; fall back to the
    repo copy (running the doctor from a checkout before installing)."""
    for d in (scripts_dir, os.path.join(REPO, "scripts")):
        if d and os.path.isfile(os.path.join(d, "qmd_search.py")):
            if d not in sys.path:
                sys.path.insert(0, d)
            try:
                import qmd_search
                return qmd_search
            except Exception:
                return None
    return None


def smoke_recall(scripts_dir):
    """Actually run the recall pipeline: qmd vsearch -> lessons/ hits.

    Returns (status, message): status in {'ok','low','empty','noqmd','error'}.
    This catches the #1 silent failure — a built-but-empty index looks identical
    to 'working, nothing matched' unless we run a query we KNOW should hit.

    Uses the same shared client (qmd_search.py, JSON mode) as the hooks themselves,
    so the smoke test exercises the REAL parse path; falls back to a legacy
    text-output parse if the module is not importable.
    """
    qs = _import_qmd_search(scripts_dir)
    if qs is not None:
        res = qs.vsearch(SMOKE_QUERY, n=8, timeout=30)
        if res["outcome"] == "no_qmd":
            return "noqmd", "qmd not on PATH"
        if res["outcome"] != "ok":
            return "error", f"qmd vsearch {res['outcome']}: {res['error']}"
        best = max((h["score"] for h in res["hits"]
                    if h["path"].startswith("lessons/")), default=0)
    else:
        # legacy fallback: parse qmd's text output directly
        qmd = shutil.which("qmd")
        if not qmd:
            return "noqmd", "qmd not on PATH"
        try:
            out = subprocess.run([qmd, "vsearch", SMOKE_QUERY],
                                 capture_output=True, text=True, timeout=30).stdout
        except Exception as e:
            return "error", f"qmd vsearch failed: {e}"
        best, cur = 0, None
        for line in out.splitlines():
            m = re.match(r"^qmd://([^\s:]+):", line)
            if m:
                cur = m.group(1)
                continue
            ms = re.match(r"^Score:\s+(\d+)", line)
            if ms and cur and cur.startswith("lessons/"):
                best = max(best, int(ms.group(1)))
    if best == 0:
        return "empty", "vsearch returned no lessons/ hits"
    if best < SMOKE_THRESHOLD:
        return "low", f"top lessons hit {best}% (below the {SMOKE_THRESHOLD}% recall threshold)"
    return "ok", f"recall fires — top lessons hit {best}%"


def mark(good):
    if not sys.stdout.isatty():
        return "[ok]" if good else "[!!]"
    return "\033[32m✓\033[0m" if good else "\033[31m✗\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-path", default=os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
    ap.add_argument("--claude-dir", default="~/.claude")
    ap.add_argument("--scripts-dir",
                    default=os.environ.get("PERSONAL_OS_SCRIPTS_DIR", "~/.personal-os/scripts"))
    args = ap.parse_args()
    vault = expand(args.vault_path)
    cd = expand(args.claude_dir)
    sd = expand(args.scripts_dir)

    problems = 0

    def check(label, good, hint=""):
        nonlocal problems
        print(f" {mark(good)}  {label}")
        if not good:
            problems += 1
            if hint:
                print(f"       → {hint}")

    def check_info(label, note):
        print(f"  ·  {label} — {note}")

    print("Personal OS — doctor (one-time post-install wiring check)")
    print("(for ongoing runtime health — recall freshness, queue/inbox backlog — run  /os doctor)\n")

    print("Dependencies:")
    check("qmd (core)", bool(shutil.which("qmd")),
          "npm install -g @tobilu/qmd")
    check("graphify (optional)", bool(shutil.which("graphify")),
          "uv tool install graphifyy")
    check("ollama (optional, /lessons-gc dedup + dreaming LLM pass)", bool(shutil.which("ollama")),
          "https://ollama.com — only needed for duplicate detection and the dream residue pass")
    check("jq (Stop-hook nudge)", bool(shutil.which("jq")), "brew install jq / apt install jq")

    print("\nVault:")
    check(f"vault at {vault}", os.path.isdir(vault))
    check("CLAUDE.md present", os.path.isfile(os.path.join(vault, "CLAUDE.md")))
    check("HOME.md present", os.path.isfile(os.path.join(vault, "HOME.md")))
    check("_templates present", os.path.isdir(os.path.join(vault, "_templates")))
    lessons = os.path.join(vault, "lessons")
    n_lessons = len([f for f in os.listdir(lessons) if f.endswith(".md")]) \
        if os.path.isdir(lessons) else 0
    check(f"lessons/ has notes ({n_lessons})", n_lessons > 0,
          "seed examples or write one with /lesson, else recall has nothing to surface")

    print("\nClaude Code integration:")
    for f in ("hooks/recall-lessons.py", "hooks/risk-recall.py", "hooks/health-sentinel.py",
              "hooks/guard.py", "hooks/session-brief.py",
              "personal-os/os_lessons.py", "personal-os/os_doctor.py",
              "personal-os/guards.example.json"):
        check(f"~/.claude/{f}", os.path.isfile(os.path.join(cd, f)))
    for cmd in ("save", "lesson", "idea", "os", "resume", "mine-chats", "lessons-gc",
                "harvest", "dream", "producer", "undo", "ask"):
        p = os.path.join(cd, "commands", cmd + ".md")
        check(f"/{cmd}", os.path.isfile(p))
    for f in ("qmd_search.py", "pos_utils.py", "pos_health.py", "pos_actions.py",
              "pos_autopilot.py", "os_dashboard.py", "preflight.sh", "dream.py",
              "dream_run.sh", "vault_autopush.sh", "graph_rebuild.sh", "save_nudge.sh"):
        check(f"scripts/{f}", os.path.isfile(os.path.join(sd, f)),
              "run install.py — the hooks import the shared modules from the scripts dir")
    guards = os.path.join(cd, "personal-os", "guards.json")
    if os.path.isfile(guards):
        try:
            json.load(open(guards))
            check("guards.json valid JSON", True)
        except Exception:
            check("guards.json valid JSON", False,
                  "malformed — guard.py fails open (no guards fire) until it parses")
    else:
        check_info("guards.json", "not materialized yet (run install.py — copies "
                                  "guards.example.json and fills git_author_email)")

    settings_blob = ""
    settings = os.path.join(cd, "settings.json")
    if os.path.isfile(settings):
        try:
            s = json.load(open(settings))
            settings_blob = json.dumps(s)
            check("settings.json: UserPromptSubmit recall hook", "recall-lessons.py" in settings_blob)
            check("settings.json: PreToolUse guard hook", "guard.py" in settings_blob)
            check("settings.json: PreToolUse risk hook", "risk-recall.py" in settings_blob)
            check("settings.json: SessionStart health sentinel", "health-sentinel.py" in settings_blob)
            check("settings.json: SessionStart project brief", "session-brief.py" in settings_blob)
            check("settings.json: PERSONAL_OS_VAULT env", "PERSONAL_OS_VAULT" in settings_blob)
        except Exception:
            check("settings.json valid JSON", False, "the file is malformed")
    else:
        check("settings.json exists", False, "run install.py")

    print("\nOptional features (checked only if enabled):")
    # Dreaming schedule: the plist existing means the user opted in — then it must be loaded.
    if platform.system() == "Darwin":
        plist = os.path.join(HOME, "Library", "LaunchAgents", "com.personal-os.dream.plist")
        if os.path.isfile(plist):
            try:
                out = subprocess.run(["launchctl", "list"], capture_output=True,
                                     text=True, timeout=10).stdout
            except Exception:
                out = ""
            check("dream launchd job loaded (com.personal-os.dream)",
                  "com.personal-os.dream" in out,
                  f"launchctl load {plist}")
        else:
            check_info("dreaming schedule", "not registered (optional — install.py --schedule-dream)")
    else:
        check_info("dreaming schedule", "non-macOS: verify your crontab/systemd timer yourself")
    # Autopush: opted in ⇔ the Stop hook references vault_autopush.sh — then a remote must exist.
    if "vault_autopush.sh" in settings_blob:
        try:
            remotes = subprocess.run(["git", "-C", vault, "remote"],
                                     capture_output=True, text=True, timeout=10).stdout.strip()
        except Exception:
            remotes = ""
        check("autopush: vault has a git remote", bool(remotes),
              "git -C <vault> remote add origin <private-repo-url> — without a remote, "
              "autopush commits but can never push")
    else:
        check_info("vault autopush", "not enabled (optional — install.py --autopush)")

    print("\nqmd index:")
    idx = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")),
                       "qmd", "index.yml")
    check(f"qmd config at {idx}", os.path.isfile(idx))

    print("\nRecall smoke test (runs a real query):")
    status, msg = smoke_recall(sd)
    if status == "ok":
        check(msg, True)
    elif status == "low":
        check(msg, False, "lower PERSONAL_OS_SCORE, or add more/closer lessons")
    elif status == "empty":
        check("recall returns a lesson", False,
              "index is empty — run:  qmd update && qmd embed")
    elif status == "noqmd":
        check("recall query", False, "install qmd first")
    else:
        check("recall query", False, msg)

    print()
    if problems == 0:
        print(mark(True), "all good — recall is firing.")
        return 0
    print(mark(False), f"{problems} issue(s) above. See docs/SETUP.md.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
