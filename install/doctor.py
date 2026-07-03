#!/usr/bin/env python3
"""Personal OS doctor — check that everything is wired up. Read-only, $0.

Usage: python3 install/doctor.py [--vault-path ~/vault] [--claude-dir ~/.claude]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
SMOKE_QUERY = "git push force overwrote a shared branch"
SMOKE_THRESHOLD = 58  # keep in sync with the recall hook


def smoke_recall():
    """Actually run the recall pipeline: qmd vsearch -> parse lessons/ hits.

    Returns (status, message): status in {'ok','low','empty','noqmd','error'}.
    This catches the #1 silent failure — a built-but-empty index looks identical
    to 'working, nothing matched' unless we run a query we KNOW should hit.
    """
    qmd = shutil.which("qmd")
    if not qmd:
        return "noqmd", "qmd not on PATH"
    try:
        out = subprocess.run([qmd, "vsearch", SMOKE_QUERY],
                             capture_output=True, text=True, timeout=30).stdout
    except Exception as e:
        return "error", f"qmd vsearch failed: {e}"
    best, cur = 0.0, None
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


def expand(p):
    return os.path.abspath(os.path.expanduser(p))


def mark(good):
    if not sys.stdout.isatty():
        return "[ok]" if good else "[!!]"
    return "\033[32m✓\033[0m" if good else "\033[31m✗\033[0m"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vault-path", default=os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
    ap.add_argument("--claude-dir", default="~/.claude")
    args = ap.parse_args()
    vault = expand(args.vault_path)
    cd = expand(args.claude_dir)

    problems = 0

    def check(label, good, hint=""):
        nonlocal problems
        print(f" {mark(good)}  {label}")
        if not good:
            problems += 1
            if hint:
                print(f"       → {hint}")

    print("Personal OS — doctor (one-time post-install wiring check)")
    print("(for ongoing runtime health — recall freshness, queue/inbox backlog — run  /os doctor)\n")

    print("Dependencies:")
    check("qmd (core)", bool(shutil.which("qmd")),
          "npm install -g @tobilu/qmd")
    check("graphify (optional)", bool(shutil.which("graphify")),
          "uv tool install graphifyy")
    check("ollama (optional, /lessons-gc dedup)", bool(shutil.which("ollama")),
          "https://ollama.com — only needed for duplicate detection")
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
    for f in ("hooks/recall-lessons.py", "hooks/risk-recall.py",
              "personal-os/os_lessons.py", "personal-os/os_doctor.py"):
        check(f"~/.claude/{f}", os.path.isfile(os.path.join(cd, f)))
    for cmd in ("save", "lesson", "idea", "os", "resume", "mine-chats", "lessons-gc", "harvest", "dream"):
        p = os.path.join(cd, "commands", cmd + ".md")
        check(f"/{cmd}", os.path.isfile(p))

    settings = os.path.join(cd, "settings.json")
    if os.path.isfile(settings):
        try:
            s = json.load(open(settings))
            blob = json.dumps(s)
            check("settings.json: UserPromptSubmit recall hook", "recall-lessons.py" in blob)
            check("settings.json: PreToolUse risk hook", "risk-recall.py" in blob)
            check("settings.json: PERSONAL_OS_VAULT env", "PERSONAL_OS_VAULT" in blob)
        except Exception:
            check("settings.json valid JSON", False, "the file is malformed")
    else:
        check("settings.json exists", False, "run install.py")

    print("\nqmd index:")
    idx = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")),
                       "qmd", "index.yml")
    check(f"qmd config at {idx}", os.path.isfile(idx))

    print("\nRecall smoke test (runs a real query):")
    status, msg = smoke_recall()
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
