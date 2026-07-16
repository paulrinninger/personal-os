#!/usr/bin/env python3
"""UserPromptSubmit hook: auto-recall vault lessons relevant to the prompt.

Reads the hook JSON on stdin, runs a fast local vector search (`qmd vsearch`,
semantic, no LLM/API, $0) over the indexed vault, keeps only lessons/ hits above
a score threshold, and injects them back as additionalContext so documented
mistakes get surfaced WITHOUT relying on Claude remembering to query them.

Quiet by design: prints nothing unless there is a real lesson match.

Parsing + fire-log go through the shared modules qmd_search.py (JSON mode — one
parser instead of four divergent ones) and pos_utils.py from the installed scripts
dir. Misses are logged too (`type`: hit|zero|timeout|error|no_qmd) — only that makes
recall precision and the cold-start timeout rate measurable at all (/os doctor,
dream fires pass).

Config (all optional, set by the installer into settings.json `env`):
  PERSONAL_OS_VAULT        vault location for display paths   (default ~/vault)
  PERSONAL_OS_SCRIPTS_DIR  where qmd_search.py/pos_utils.py live
                                              (default ~/.personal-os/scripts)
  PERSONAL_OS_LOG_DIR      debug log dir   (default $XDG_STATE_HOME/personal-os/logs)
  PERSONAL_OS_HOME         dir holding lesson-fires.jsonl  (default ~/.claude/personal-os)
  PERSONAL_OS_LANG         en | de   (default en)  — language of the injected note
"""
import json
import os
import sys

VAULT_DISPLAY = os.environ.get("PERSONAL_OS_VAULT", "~/vault").rstrip("/")
LANG = (os.environ.get("PERSONAL_OS_LANG", "en") or "en").lower()[:2]
SCORE_THRESHOLD = int(os.environ.get("PERSONAL_OS_SCORE", "58"))  # vector-sim %, below = silent
MAX_LESSONS = 3
MIN_PROMPT_LEN = 12    # skip "ok", "ja", trivial acks
SEARCH_TIMEOUT = 9     # s; warm ~2s, cold-start (model load) may exceed -> miss-log

# Shared modules live in the installed scripts dir (the installer wires
# PERSONAL_OS_SCRIPTS_DIR into the hook command line; the fallback is the
# installer's default scripts dir).
sys.path.insert(0, os.path.expanduser(
    os.environ.get("PERSONAL_OS_SCRIPTS_DIR", "~/.personal-os/scripts")))
try:
    import pos_utils
    import qmd_search
except Exception:
    pos_utils = qmd_search = None


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
    if qmd_search is None:
        return log("shared modules (qmd_search/pos_utils) not importable — recall off; "
                   "check PERSONAL_OS_SCRIPTS_DIR")
    query = prompt.replace("\n", " ")[:300]
    snippet60 = prompt[:60].replace("\n", " ")

    def miss(mtype, extra=None):
        rec = {"type": mtype, "trigger": "UserPromptSubmit", "prompt": snippet60}
        if extra:
            rec.update(extra)
        pos_utils.fire_log_append(rec, fire_log=FIRE_LOG)

    res = qmd_search.vsearch(query, n=8, timeout=SEARCH_TIMEOUT)
    if res["outcome"] != "ok":
        miss(res["outcome"], {"error": res["error"]})
        return

    # Dedup by path (highest score wins), threshold, top N
    lessons = [h for h in res["hits"] if h["path"].startswith("lessons/")]
    best = {}
    for h in lessons:
        p = h["path"]
        if p not in best or h["score"] > best[p]["score"]:
            best[p] = h
    sel = sorted(
        (h for h in best.values() if h["score"] >= SCORE_THRESHOLD),
        key=lambda x: -x["score"],
    )[:MAX_LESSONS]
    if not sel:
        miss("zero", {"top_score": max((h["score"] for h in lessons), default=0)})
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
    for m in sel:
        pos_utils.fire_log_append({
            "type": "hit", "path": m["path"], "score": m["score"],
            "trigger": "UserPromptSubmit", "prompt": snippet60,
        }, fire_log=FIRE_LOG)


if __name__ == "__main__":
    main()
