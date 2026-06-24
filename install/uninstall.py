#!/usr/bin/env python3
"""Personal OS uninstaller — reverse what install.py did. Conservative by default.

Removes: our hook groups + env keys from settings.json, our commands/hooks/engine,
the scripts dir, our CLAUDE.md block, the launchd job. LEAVES your vault and the
external tools (qmd/graphify/ollama) in place.

Usage:
  python3 install/uninstall.py                 # remove the integration, keep the vault
  python3 install/uninstall.py --vault-path ~/vault --purge   # also delete the vault (2nd confirm)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HOME = os.path.expanduser("~")
HOOK_SENTINELS = (
    "recall-lessons.py", "risk-recall.py", "save_nudge.sh",
    "checkpoint session log", "graphify: knowledge graph at graphify-out",
)
ENV_KEYS = ("PERSONAL_OS_VAULT", "PERSONAL_OS_CLAUDE_DIR", "PERSONAL_OS_SCRIPTS_DIR",
            "PERSONAL_OS_LOG_DIR", "PERSONAL_OS_HOME", "PERSONAL_OS_OLLAMA", "PERSONAL_OS_LANG")
START, END = "<!-- personal-os:start -->", "<!-- personal-os:end -->"


def expand(p):
    return os.path.abspath(os.path.expanduser(p))


def info(s): print(" •", s)
def ok(s):   print(" ✓", s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--claude-dir", default="~/.claude")
    ap.add_argument("--scripts-dir", default="~/.personal-os/scripts")
    ap.add_argument("--vault-path", default="~/vault")
    ap.add_argument("--purge", action="store_true", help="also delete the vault")
    ap.add_argument("--yes", "-y", action="store_true")
    args = ap.parse_args()
    cd = expand(args.claude_dir)

    if not args.yes:
        if input("Remove the Personal OS integration (your vault stays)? [y/N] ").strip().lower() \
                not in ("y", "yes"):
            print("aborted."); return 1

    # settings.json: strip our hook groups + env keys
    sp = os.path.join(cd, "settings.json")
    if os.path.isfile(sp):
        try:
            s = json.load(open(sp))
        except Exception:
            s = None
        if s is not None:
            for event, groups in list(s.get("hooks", {}).items()):
                s["hooks"][event] = [g for g in groups
                                     if not any(t in json.dumps(g) for t in HOOK_SENTINELS)]
                if not s["hooks"][event]:
                    del s["hooks"][event]
            for k in ENV_KEYS:
                s.get("env", {}).pop(k, None)
            json.dump(s, open(sp, "w"), indent=2, ensure_ascii=False)
            ok("settings.json cleaned")

    # CLAUDE.md: remove our block
    cm = os.path.join(cd, "CLAUDE.md")
    if os.path.isfile(cm):
        t = open(cm).read()
        if START in t and END in t:
            t = (t.split(START)[0].rstrip() + "\n" + t.split(END, 1)[1].lstrip()).strip() + "\n"
            open(cm, "w").write(t)
            ok("CLAUDE.md section removed")

    # commands / hooks / engine
    for f in ("commands/save.md", "commands/lesson.md", "commands/idea.md", "commands/os.md",
              "commands/resume.md", "commands/mine-chats.md", "commands/lessons-gc.md",
              "commands/harvest.md",
              "hooks/recall-lessons.py", "hooks/risk-recall.py",
              "personal-os/os_lessons.py", "personal-os/os_doctor.py", "personal-os/README.md"):
        p = os.path.join(cd, f)
        if os.path.lexists(p):
            os.remove(p)
    ok("commands / hooks / engine removed")

    # scripts dir
    sd = expand(args.scripts_dir)
    if os.path.isdir(sd):
        shutil.rmtree(sd, ignore_errors=True)
        ok(f"scripts removed ({sd})")

    # launchd job (macOS)
    plist = os.path.join(HOME, "Library", "LaunchAgents", "com.personal-os.graph-rebuild.plist")
    if os.path.isfile(plist):
        subprocess.run(["launchctl", "unload", plist], capture_output=True)
        os.remove(plist)
        ok("nightly graph job removed")

    info("Left in place: your vault, qmd/graphify/ollama, lesson-fires log, qmd index.")
    info("Note: the qmd index config at ~/.config/qmd/index.yml was left (delete manually if unused).")

    if args.purge:
        vault = expand(args.vault_path)
        if os.path.isdir(vault):
            if args.yes or input(f"DELETE the vault and all your notes at {vault}? [y/N] ")\
                    .strip().lower() in ("y", "yes"):
                shutil.rmtree(vault, ignore_errors=True)
                ok(f"vault deleted ({vault})")

    print("\nUninstalled.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
