#!/usr/bin/env python3
"""Personal-OS runtime doctor — deterministic self-health check. Local, $0, read-only.

Checks that a LIVE Personal OS is healthy: recall hooks firing, key scripts/hooks
present, settings wired, qmd index fresh, optional nightly maintenance, lessons not
rotting, vault backed up, harvest queue drained, inbox reviewed. Run it via
`/os doctor`, and the nightly graph rebuild runs it too. Exit 1 ONLY on a real FAIL,
so a scheduled run can alert; optional/unconfigured features degrade to INFO, never FAIL.

This is distinct from `install/doctor.py` (the one-time post-install wiring smoke test).

Config (env, all optional — same vars as the hooks):
  PERSONAL_OS_HOME        engine dir + fire-log + harvest queue (default ~/.claude/personal-os)
  PERSONAL_OS_VAULT       vault location                        (default ~/vault)
  PERSONAL_OS_CLAUDE_DIR  Claude Code dir (hooks, settings)     (default ~/.claude)
  PERSONAL_OS_SCRIPTS_DIR script dir                            (default ~/.personal-os/scripts)
  PERSONAL_OS_LOG_DIR     log dir (XDG by default)
  PERSONAL_OS_GRAPH_LABEL nightly scheduler label               (default com.personal-os.graph-rebuild)
  PERSONAL_OS_LANG        en | de                               (default en)
"""
import datetime as dt
import glob
import json
import os
import platform
import subprocess
import sys

LANG = (os.environ.get("PERSONAL_OS_LANG", "en") or "en").lower()[:2]


def _exp(p):
    return os.path.abspath(os.path.expanduser(os.path.expandvars(p)))


PO = _exp(os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os"))
VAULT = _exp(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
CLAUDE_DIR = _exp(os.environ.get("PERSONAL_OS_CLAUDE_DIR", "~/.claude"))
SCRIPTS_DIR = _exp(os.environ.get("PERSONAL_OS_SCRIPTS_DIR", "~/.personal-os/scripts"))
GRAPH_LABEL = os.environ.get("PERSONAL_OS_GRAPH_LABEL", "com.personal-os.graph-rebuild")


def _log_dir():
    p = os.environ.get("PERSONAL_OS_LOG_DIR")
    if not p:
        base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
        p = os.path.join(base, "personal-os", "logs")
    return _exp(p)


def _qmd_index():
    base = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
    return os.path.join(_exp(base), "qmd", "index.sqlite")


# reuse the lesson health engine wherever it lives (same dir, or the installed PERSONAL_OS_HOME)
for _d in (os.path.dirname(os.path.abspath(__file__)), PO):
    if _d not in sys.path:
        sys.path.insert(0, _d)
try:
    import os_lessons
except Exception:
    os_lessons = None

S = {
    "en": {
        "title": "PERSONAL-OS DOCTOR",
        "recall": "Recall hooks firing", "recall_none": "no recall yet — submit a prompt to start",
        "recall_7d": "{} hits / 7d (total {})", "recall_stale": "no hits in 7d",
        "script": "Script: {}", "missing": "MISSING",
        "settings": "settings.json wires hooks", "settings_bad": "hook reference missing",
        "qmd": "qmd index fresh", "qmd_none": "not built yet (run: qmd update && qmd embed)",
        "qmd_age": "updated {}h ago",
        "nightly": "Nightly maintenance", "nightly_none": "not scheduled (optional)",
        "nightly_age": "last run {}h ago",
        "sched": "Maintenance scheduler", "sched_off": "not scheduled (optional)",
        "sched_skip": "check skipped (non-macOS)", "sched_ok": "loaded",
        "lessons": "Lessons store", "lessons_noimport": "os_lessons engine not importable",
        "lessons_x": "{} lessons | never fired: {} | archive cand.: {}",
        "review": "Lessons fresh (review_by)", "review_ok": "none overdue",
        "review_due": "{} overdue → /lessons-gc",
        "backup": "Vault backed up", "backup_none": "vault not under git (optional)",
        "backup_age": "last commit {}h ago",
        "queue": "Harvest queue", "queue_empty": "empty",
        "queue_wait": "{} session(s) waiting → /harvest",
        "inbox": "Inbox drafts", "inbox_none": "none open",
        "inbox_n": "{} draft(s) → /harvest review",
        "dream": "Dreaming (nightly)", "dream_none": "not scheduled (optional)",
        "dream_off": "disabled via dream.off (intentional)",
        "dream_age": "last activity {}h ago",
        "verdict": "{}: {} FAIL · {} WARN · {} OK",
    },
    "de": {
        "title": "PERSONAL-OS DOCTOR",
        "recall": "Recall-Hooks feuern", "recall_none": "noch kein Recall — einen Prompt absetzen",
        "recall_7d": "{} Treffer / 7d (gesamt {})", "recall_stale": "keine Treffer in 7d",
        "script": "Script: {}", "missing": "FEHLT",
        "settings": "settings.json verdrahtet Hooks", "settings_bad": "Hook-Referenz fehlt",
        "qmd": "qmd-Index frisch", "qmd_none": "noch nicht gebaut (qmd update && qmd embed)",
        "qmd_age": "vor {}h aktualisiert",
        "nightly": "Nightly-Wartung", "nightly_none": "nicht geplant (optional)",
        "nightly_age": "letzter Lauf vor {}h",
        "sched": "Wartungs-Scheduler", "sched_off": "nicht geplant (optional)",
        "sched_skip": "übersprungen (nicht macOS)", "sched_ok": "geladen",
        "lessons": "Lessons-Bestand", "lessons_noimport": "os_lessons-Engine nicht importierbar",
        "lessons_x": "{} Lessons | nie gefeuert: {} | Archiv-Kand.: {}",
        "review": "Lessons aktuell (review_by)", "review_ok": "keine überfällig",
        "review_due": "{} überfällig → /lessons-gc",
        "backup": "Vault gesichert", "backup_none": "Vault nicht unter git (optional)",
        "backup_age": "letzter Commit vor {}h",
        "queue": "Harvest-Queue", "queue_empty": "leer",
        "queue_wait": "{} Session(s) warten → /harvest",
        "inbox": "Inbox-Drafts", "inbox_none": "keine offen",
        "inbox_n": "{} Draft(s) → /harvest review",
        "dream": "Dreaming (nightly)", "dream_none": "nicht geplant (optional)",
        "dream_off": "per dream.off deaktiviert (bewusst)",
        "dream_age": "letzte Aktivität vor {}h",
        "verdict": "{}: {} FAIL · {} WARN · {} OK",
    },
}


def t(k):
    return S.get(LANG, S["en"]).get(k, S["en"].get(k, k))


NOW = dt.datetime.now()
checks = []   # (status, name, detail) ; status in PASS/WARN/FAIL/INFO


def add(status, name, detail=""):
    checks.append((status, name, detail))


def age_h(path):
    try:
        return (NOW - dt.datetime.fromtimestamp(os.path.getmtime(path))).total_seconds() / 3600
    except Exception:
        return None


# 1) recall hooks firing (fire-log fresh) — WARN (never FAIL) on a fresh install
fire = os.path.join(PO, "lesson-fires.jsonl")
if os.path.exists(fire):
    total = d7 = 0
    for line in open(fire, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        total += 1
        try:
            if (NOW - dt.datetime.fromisoformat(json.loads(line).get("ts", ""))).days <= 7:
                d7 += 1
        except Exception:
            pass
    add("PASS" if d7 else "WARN", t("recall"),
        t("recall_7d").format(d7, total) if d7 else t("recall_stale"))
else:
    add("WARN", t("recall"), t("recall_none"))

# 2) key hooks + scripts present (real post-install invariants)
for d, fn in [(CLAUDE_DIR, "hooks/recall-lessons.py"), (CLAUDE_DIR, "hooks/risk-recall.py"),
              (SCRIPTS_DIR, "graph_rebuild.sh"), (SCRIPTS_DIR, "save_nudge.sh")]:
    p = os.path.join(d, fn)
    add("PASS" if os.path.exists(p) else "FAIL", t("script").format(os.path.basename(fn)),
        "" if os.path.exists(p) else t("missing"))

# 3) settings.json wires the recall hooks
try:
    s = open(os.path.join(CLAUDE_DIR, "settings.json"), encoding="utf-8").read()
    ok = "recall-lessons.py" in s and "risk-recall.py" in s
    add("PASS" if ok else "FAIL", t("settings"), "" if ok else t("settings_bad"))
except Exception:
    add("WARN", t("settings"), t("settings_bad"))

# 4) qmd index — INFO if not built yet (fresh install), never FAIL
qi = _qmd_index()
ah = age_h(qi)
if ah is None:
    add("INFO", t("qmd"), t("qmd_none"))
else:
    add("PASS", t("qmd"), t("qmd_age").format(int(ah)))

# 5) nightly maintenance — optional; INFO if never ran
glog = os.path.join(_log_dir(), "graph-rebuild.log")
ah = age_h(glog)
if ah is None:
    add("INFO", t("nightly"), t("nightly_none"))
else:
    add("PASS", t("nightly"), t("nightly_age").format(int(ah)))

# 6) maintenance scheduler — macOS only, optional; never FAIL/WARN
if platform.system() == "Darwin":
    try:
        out = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10).stdout
        loaded = GRAPH_LABEL in out
        add("PASS" if loaded else "INFO", t("sched"), t("sched_ok") if loaded else t("sched_off"))
    except Exception:
        add("INFO", t("sched"), t("sched_off"))
else:
    add("INFO", t("sched"), t("sched_skip"))

# 7) lessons health (reuse os_lessons.analyze)
if os_lessons:
    try:
        lessons, cold, _stale = os_lessons.analyze(90)
        never = sum(1 for l in lessons if l["fired"] == 0)
        add("PASS", t("lessons"), t("lessons_x").format(len(lessons), never, len(cold)))
        stale = _stale
        add("PASS" if not stale else "WARN", t("review"),
            t("review_ok") if not stale else t("review_due").format(len(stale)))
    except Exception:
        add("WARN", t("lessons"), t("lessons_noimport"))
else:
    add("WARN", t("lessons"), t("lessons_noimport"))

# 8) vault backed up — optional (vault git is the user's choice); INFO if not a repo
if os.path.isdir(os.path.join(VAULT, ".git")):
    try:
        r = subprocess.run(["git", "-C", VAULT, "log", "-1", "--format=%ct"],
                           capture_output=True, text=True, timeout=10).stdout.strip()
        if r:
            ah = (NOW - dt.datetime.fromtimestamp(int(r))).total_seconds() / 3600
            add("PASS", t("backup"), t("backup_age").format(int(ah)))
        else:
            add("INFO", t("backup"), t("backup_none"))
    except Exception:
        add("INFO", t("backup"), t("backup_none"))
else:
    add("INFO", t("backup"), t("backup_none"))

# 9) harvest queue drained
hq = os.path.join(PO, "harvest-queue.jsonl")
n = sum(1 for l in open(hq, encoding="utf-8", errors="replace") if l.strip()) if os.path.exists(hq) else 0
add("PASS" if n == 0 else "WARN", t("queue"), t("queue_empty") if n == 0 else t("queue_wait").format(n))

# 10) inbox drafts reviewed (dreams/ has its own /dream review lifecycle — don't double-count)
inbox = [p for p in glob.glob(os.path.join(VAULT, "_inbox", "**", "*.md"), recursive=True)
         if os.sep + "dreams" + os.sep not in p]
add("PASS" if not inbox else "WARN", t("inbox"),
    t("inbox_none") if not inbox else t("inbox_n").format(len(inbox)))

# 11) dreaming ran — optional, INFO if never configured, never FAIL
if os.path.exists(os.path.join(PO, "dream.off")):
    add("INFO", t("dream"), t("dream_off"))
else:
    dreams = sorted(glob.glob(os.path.join(VAULT, "_inbox", "dreams", "*-dream.md")))
    dream_note_age = age_h(dreams[-1]) if dreams else None
    dream_log_age = age_h(os.path.join(_log_dir(), "dream.log"))
    candidates = [a for a in (dream_note_age, dream_log_age) if a is not None]
    if not candidates:
        add("INFO", t("dream"), t("dream_none"))
    else:
        best = min(candidates)
        add("PASS" if best < 36 else "WARN", t("dream"), t("dream_age").format(int(best)))

# --- report ---
ICON = {"PASS": "✓", "WARN": "⚠", "FAIL": "✗", "INFO": "·"}
fails = [c for c in checks if c[0] == "FAIL"]
warns = [c for c in checks if c[0] == "WARN"]
oks = [c for c in checks if c[0] in ("PASS", "INFO")]
print("{} ({:%Y-%m-%d %H:%M})".format(t("title"), NOW))
for st, name, detail in checks:
    print("  {} {}".format(ICON[st], name) + (" — {}".format(detail) if detail else ""))
verdict = "FAIL" if fails else ("WARN" if warns else "OK")
print("\n  → " + t("verdict").format(verdict, len(fails), len(warns), len(oks)))
sys.exit(1 if fails else 0)
