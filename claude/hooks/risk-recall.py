#!/usr/bin/env python3
"""PreToolUse hook: recall lessons right BEFORE a risky / outward action.

Second tier of the Personal-OS recall loop. The UserPromptSubmit hook catches
intent at prompt time; this catches the *action moment* — the irreversible or
outward steps where a repeated mistake actually costs something:
  - Bash: git push/--force, rm -rf, reset --hard, deploy/vercel, db drop/delete, …
  - Mail/MCP: create_draft / send_message / send_email / …

Semantic recall via `qmd vsearch` (local, $0). Injects matching lessons as
PreToolUse additionalContext (informational — never blocks). Quiet otherwise.
Shares the fire-log with the prompt-time hook (trigger marks which tier fired).

Config: see recall-lessons.py (same PERSONAL_OS_* env vars).
"""
import datetime
import json
import os
import re
import shutil
import subprocess
import sys

VAULT_DISPLAY = os.environ.get("PERSONAL_OS_VAULT", "~/vault").rstrip("/")
LANG = (os.environ.get("PERSONAL_OS_LANG", "en") or "en").lower()[:2]
SCORE_THRESHOLD = int(os.environ.get("PERSONAL_OS_SCORE", "58"))
MAX_LESSONS = 3
SEARCH_TIMEOUT = 9


def _personal_os_home():
    return os.path.expanduser(
        os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os"))


def _log_path():
    p = os.environ.get("PERSONAL_OS_LOG_DIR")
    if not p:
        base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        p = os.path.join(base, "personal-os", "logs")
    return os.path.join(os.path.expanduser(p), "hooks.log")


FIRE_LOG = os.path.join(_personal_os_home(), "lesson-fires.jsonl")
LOG = _log_path()

RISKY_BASH = re.compile(
    r"git\s+push|--force|--force-with-lease|reset\s+--hard|\brm\s+-[rf]|"
    r"\bvercel\b|\bdeploy\b|npm\s+publish|yarn\s+publish|gh\s+release|"
    r"drop\s+table|delete\s+from|truncate\b|supabase\s+db|"
    r"prisma\s+migrate\s+(reset|deploy)|git\s+clean\s+-|chmod\s+-R|"
    r"curl[^|]*\b(api|/v1/|amazonaws|stripe|openai)\b",
    re.I,
)
MAIL_KEYS = ("create_draft", "send_message", "send_email", "send_mail",
             "sendmessage", "send_draft")

STRINGS = {
    "en": {
        "header": ("VAULT LESSONS — you are about to run a risky/outward action ({}). "
                   "Check these documented mistakes FIRST and apply them:"),
        "footer": "Read: `qmd get <#docid>` or open the path.",
    },
    "de": {
        "header": ("VAULT-LESSONS — du bist dabei, eine riskante/ausgehende Aktion "
                   "auszuführen ({}). Prüfe ZUERST diese dokumentierten Fehler und "
                   "wende sie an:"),
        "footer": "Lesen: `qmd get <#docid>` oder Read auf den Pfad.",
    },
}


def t(key):
    return STRINGS.get(LANG, STRINGS["en"]).get(key, STRINGS["en"][key])


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write("[risk-recall] " + msg + "\n")
    except Exception:
        pass


def extract_query(data):
    """Return (query_text, label) for a risky action, else (None, None)."""
    tool = (data.get("tool_name") or "")
    ti = data.get("tool_input") or {}
    cmd = ti.get("command")
    if cmd and ("Bash" in tool or not tool):
        if RISKY_BASH.search(cmd):
            return cmd[:300], "Bash"
        return None, None
    low = tool.lower()
    if any(k in low for k in MAIL_KEYS):
        # The risk lives in the ACT of mailing (link-wrapping, draft status,
        # client rendering), not the body topic — seed with email-mechanics
        # terms so vsearch surfaces email lessons regardless of content.
        seed = ("email send draft link signature attachment mail-client "
                "formatting outreach versenden entwurf")
        subj = str(ti.get("subject") or "")
        return (seed + " " + subj)[:300], tool.split("__")[-1] or "mail"
    return None, None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    query, label = extract_query(data)
    if not query:
        return

    qmd = shutil.which("qmd")
    if not qmd:
        return
    try:
        out = subprocess.run([qmd, "vsearch", query],
                             capture_output=True, text=True, timeout=SEARCH_TIMEOUT).stdout
    except Exception:
        return

    matches, cur = [], None
    head = re.compile(r"^qmd://([^\s:]+):(\d+)\s+#(\S+)")

    def flush(c):
        if c and c["path"].startswith("lessons/"):
            matches.append(c)

    for line in out.splitlines():
        m = head.match(line)
        if m:
            flush(cur)
            cur = {"path": m.group(1), "docid": m.group(3), "score": 0, "snippet": ""}
            continue
        if cur is None:
            continue
        ms = re.match(r"^Score:\s+(\d+)", line)
        if ms:
            cur["score"] = int(ms.group(1))
            continue
        s = line.strip()
        if s and not cur["snippet"] and not s.startswith("@@") \
                and not s.startswith("Title:") and not s.startswith("##"):
            if s.startswith("- ") or len(s) > 8:
                cur["snippet"] = s[:200]
    flush(cur)

    best = {}
    for mm in matches:
        p = mm["path"]
        if p not in best or mm["score"] > best[p]["score"]:
            best[p] = mm
    sel = sorted((m for m in best.values() if m["score"] >= SCORE_THRESHOLD),
                 key=lambda x: -x["score"])[:MAX_LESSONS]
    if not sel:
        return

    lines = [t("header").format(label)]
    for m in sel:
        lines.append("• {}/{}  (#{}, {}%)".format(
            VAULT_DISPLAY, m["path"], m["docid"], m["score"]))
        if m["snippet"]:
            lines.append("   ↳ " + m["snippet"])
    lines.append(t("footer"))

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "additionalContext": "\n".join(lines),
        }
    }))
    log("injected {} lesson(s) before {}; top={} score={}".format(
        len(sel), label, sel[0]["path"], sel[0]["score"]))
    try:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        os.makedirs(os.path.dirname(FIRE_LOG), exist_ok=True)
        with open(FIRE_LOG, "a", encoding="utf-8") as f:
            for m in sel:
                f.write(json.dumps({
                    "ts": ts, "path": m["path"], "score": m["score"],
                    "trigger": "PreToolUse:" + label, "prompt": query[:60],
                }, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
