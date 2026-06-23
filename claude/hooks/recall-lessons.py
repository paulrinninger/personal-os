#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-recall vault lessons relevant to the prompt.

Reads the hook JSON on stdin, runs a fast local vector search (`qmd vsearch`,
semantic, no LLM/API, $0) over the indexed vault, keeps only lessons/ hits above
a score threshold, and injects them back as additionalContext so documented
mistakes get surfaced WITHOUT relying on Claude remembering to query them.

Quiet by design: prints nothing unless there is a real lesson match.

Config (all optional, set by the installer into settings.json `env`):
  PERSONAL_OS_VAULT     vault location for display paths   (default ~/vault)
  PERSONAL_OS_LOG_DIR   debug log dir   (default $XDG_STATE_HOME/personal-os/logs)
  PERSONAL_OS_HOME      dir holding lesson-fires.jsonl  (default ~/.claude/personal-os)
  PERSONAL_OS_LANG      en | de   (default en)  — language of the injected note
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
SCORE_THRESHOLD = int(os.environ.get("PERSONAL_OS_SCORE", "58"))  # vector-sim %, below = silent
MAX_LESSONS = 3
MIN_PROMPT_LEN = 12    # skip "ok", "ja", trivial acks
SEARCH_MODE = "vsearch"  # semantic, local model, no API ($0)
SEARCH_TIMEOUT = 9       # s; warm ~2s, cold-start (model load) may exceed -> skip


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

# Bilingual UI strings. The injected note is what Claude (and the user) sees.
STRINGS = {
    "en": {
        "header": ("VAULT LESSONS (auto-match for this request) — BEFORE you act, "
                   "read the relevant lesson(s) and apply them so documented "
                   "mistakes are not repeated:"),
        "footer": "Read: `qmd get <#docid>` or open the path.",
    },
    "de": {
        "header": ("VAULT-LESSONS (automatischer Treffer zu dieser Anfrage) — BEVOR "
                   "du handelst, lies die relevante(n) Lesson(s) und wende sie an, "
                   "damit dokumentierte Fehler nicht wiederholt werden:"),
        "footer": "Lesen: `qmd get <#docid>` oder Read auf den Pfad.",
    },
}


def t(key):
    return STRINGS.get(LANG, STRINGS["en"]).get(key, STRINGS["en"][key])


def log(msg):
    try:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        with open(LOG, "a") as f:
            f.write("[recall-lessons] " + msg + "\n")
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    prompt = (data.get("prompt") or "").strip()
    if len(prompt) < MIN_PROMPT_LEN:
        return
    query = prompt.replace("\n", " ")[:300]

    qmd = shutil.which("qmd")
    if not qmd:
        return
    try:
        out = subprocess.run(
            [qmd, SEARCH_MODE, query],
            capture_output=True, text=True, timeout=SEARCH_TIMEOUT,
        ).stdout
    except Exception:
        return

    # Parse qmd blocks:  qmd://<path>:<line> #<docid> / Score: N% / snippet
    # IMPORTANT: reset on EVERY qmd:// header (not just lessons), otherwise a
    # following ideas/knowledge/logs block leaks its Score into the lesson.
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

    # Dedup by path (highest score wins), threshold, top N
    best = {}
    for mm in matches:
        p = mm["path"]
        if p not in best or mm["score"] > best[p]["score"]:
            best[p] = mm
    sel = sorted(
        (m for m in best.values() if m["score"] >= SCORE_THRESHOLD),
        key=lambda x: -x["score"],
    )[:MAX_LESSONS]
    if not sel:
        return

    lines = [t("header")]
    for m in sel:
        lines.append("• {}/{}  (#{}, {}%)".format(
            VAULT_DISPLAY, m["path"], m["docid"], m["score"]))
        if m["snippet"]:
            lines.append("   ↳ " + m["snippet"])
    lines.append(t("footer"))
    ctx = "\n".join(lines)

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": ctx,
        }
    }))
    log("injected {} lesson(s); top={} score={}".format(
        len(sel), sel[0]["path"], sel[0]["score"]))

    # Measure loop: one append-only line per injected lesson (powers /os + /lessons-gc).
    try:
        ts = datetime.datetime.now().isoformat(timespec="seconds")
        os.makedirs(os.path.dirname(FIRE_LOG), exist_ok=True)
        snippet = prompt[:60].replace("\n", " ")
        with open(FIRE_LOG, "a", encoding="utf-8") as f:
            for m in sel:
                f.write(json.dumps({
                    "ts": ts, "path": m["path"], "score": m["score"],
                    "trigger": "UserPromptSubmit", "prompt": snippet,
                }, ensure_ascii=False) + "\n")
    except Exception:
        pass


if __name__ == "__main__":
    main()
