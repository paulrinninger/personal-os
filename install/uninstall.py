#!/usr/bin/env python3
"""Personal OS uninstaller — reverse what install.py did. Conservative by default.

Removes: our hook groups + env keys from settings.json, our commands/hooks/engine,
the scripts dir, our CLAUDE.md block, the launchd jobs (graph rebuild + dream), and
the dreaming engine's state files. LEAVES your vault (including any dream notes in
<vault>/_inbox/dreams/ — those are your content) and the external tools
(qmd/graphify/ollama) in place.

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
    "recall-lessons.py", "risk-recall.py", "save_nudge.sh", "health-sentinel.py",
    "vault_autopush.sh", "dream_run.sh", "guard.py", "session-brief.py",
    "checkpoint session log", "graphify: knowledge graph at graphify-out",
)
ENV_KEYS = ("PERSONAL_OS_VAULT", "PERSONAL_OS_CLAUDE_DIR", "PERSONAL_OS_SCRIPTS_DIR",
            "PERSONAL_OS_LOG_DIR", "PERSONAL_OS_HOME", "PERSONAL_OS_OLLAMA",
            "PERSONAL_OS_DREAM_MODEL", "PERSONAL_OS_LANG")
START, END = "<!-- personal-os:start -->", "<!-- personal-os:end -->"
LAUNCHD_LABELS = ("com.personal-os.graph-rebuild", "com.personal-os.dream")


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
    state_home = os.path.join(cd, "personal-os")  # install.py's default personal_os_home

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
              "commands/harvest.md", "commands/dream.md", "commands/producer.md",
              "commands/undo.md", "commands/ask.md",
              "hooks/recall-lessons.py", "hooks/risk-recall.py", "hooks/health-sentinel.py",
              "hooks/guard.py", "hooks/session-brief.py",
              "personal-os/os_lessons.py", "personal-os/os_doctor.py",
              "personal-os/guards.example.json", "personal-os/README.md"):
        p = os.path.join(cd, f)
        if os.path.lexists(p):
            os.remove(p)
    ok("commands / hooks / engine removed")

    # scripts dir
    sd = expand(args.scripts_dir)
    if os.path.isdir(sd):
        shutil.rmtree(sd, ignore_errors=True)
        ok(f"scripts removed ({sd})")

    # launchd jobs (macOS): graph rebuild + dream
    for label in LAUNCHD_LABELS:
        plist = os.path.join(HOME, "Library", "LaunchAgents", label + ".plist")
        if os.path.isfile(plist):
            subprocess.run(["launchctl", "unload", plist], capture_output=True)
            os.remove(plist)
            ok(f"nightly job removed ({label})")

    # dreaming engine + install state (under the state home). Dream NOTES in
    # <vault>/_inbox/dreams/ and producer drafts in _inbox/producer-drafts/ are user
    # content and stay — as do producer-queue.jsonl / producer-templates.json (you
    # authored those, they are lead data, not engine state). guards.json stays too
    # (user-customized rules), and so do actions.jsonl + harvest-queue-done.jsonl:
    # they are the autopilot's undo journal — deleting them would take away your
    # ability to roll back actions the autopilot already took in the vault.
    for f in ("dream-cursor.json", "dream-embeds.json", "dream-feedback.jsonl",
              "ventures-cursor.json", "ventures-embeds.json", "producer-feedback.jsonl",
              "feedback-scan.json", "dream.off", "autopilot.off",
              "install-manifest.json", "health.json"):
        p = os.path.join(state_home, f)
        if os.path.lexists(p):
            os.remove(p)
    for d in ("dream-work", "health", "locks"):
        p = os.path.join(state_home, d)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
    ok("dream/health state removed")

    info("Left in place: your vault (incl. dream notes in _inbox/dreams/ and producer "
         "drafts), producer queue/templates (your lead data), guards.json (your "
         "compiled rules), actions.jsonl + harvest-queue-done.jsonl (the autopilot's "
         "undo journal), qmd/graphify/ollama, lesson-fires log, qmd index.")
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
