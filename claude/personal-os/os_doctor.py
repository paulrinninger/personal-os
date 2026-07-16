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
        "misses": "Recall misses (7d)",
        "misses_x": "{} zero-hit · {} timeout · {} error",
        "misses_hint": " — many timeouts: qmd cold start?",
        "steps": "Nightly steps: {}", "steps_fail": "failed: {}", "steps_ok": "{} steps green",
        "steps_none": "no health.json yet (nightly jobs not scheduled/run — optional)",
        "refs": "Refs queue", "refs_n": "{} cards",
        "refs_over": "{} cards — >150, review the inbox before adding more",
        "mining": "Chat mining", "mining_none": "no chat imports (optional)",
        "mining_n": "{} chats not yet mined",
        "mining_over": "{} chats not yet mined — run /mine-chats (batches of 10)",
        "dreamnotes": "Dream notes", "dreamnotes_n": "{} unreviewed",
        "dreamnotes_over": "{} unreviewed — run /dream review",
        "dream": "Dreaming (nightly)", "dream_none": "not scheduled (optional)",
        "dream_off": "disabled via dream.off (intentional)",
        "dream_age": "last activity {}h ago",
        "autopush": "Vault autopush", "autopush_off": "not enabled (optional)",
        "autopush_ok": "Stop hook wired, vault remote configured",
        "autopush_noremote": "Stop hook wired but the vault has NO git remote — nothing can be pushed",
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
        "verdict": "{}: {} FAIL · {} WARN · {} OK",
    },
    "de": {
        "title": "PERSONAL-OS DOCTOR",
        "recall": "Recall-Hooks feuern", "recall_none": "noch kein Recall — einen Prompt absetzen",
        "recall_7d": "{} Treffer / 7d (gesamt {})", "recall_stale": "keine Treffer in 7d",
        "misses": "Recall-Misses (7d)",
        "misses_x": "{} zero-hit · {} Timeout · {} Fehler",
        "misses_hint": " — viele Timeouts: qmd-Cold-Start?",
        "steps": "Nightly-Steps: {}", "steps_fail": "fehlgeschlagen: {}", "steps_ok": "{} Steps grün",
        "steps_none": "noch keine health.json (Nightly-Jobs nicht geplant/gelaufen — optional)",
        "refs": "Refs-Queue", "refs_n": "{} Karten",
        "refs_over": "{} Karten — >150, erst die Inbox reviewen",
        "mining": "Chat-Mining", "mining_none": "keine Chat-Importe (optional)",
        "mining_n": "{} Chats unvermint",
        "mining_over": "{} Chats unvermint — /mine-chats fahren (Batches à 10)",
        "dreamnotes": "Traum-Notizen", "dreamnotes_n": "{} unreviewt",
        "dreamnotes_over": "{} unreviewt — /dream review fahren",
        "dream": "Dreaming (nightly)", "dream_none": "nicht geplant (optional)",
        "dream_off": "per dream.off deaktiviert (bewusst)",
        "dream_age": "letzte Aktivität vor {}h",
        "autopush": "Vault-Autopush", "autopush_off": "nicht aktiviert (optional)",
        "autopush_ok": "Stop-Hook verdrahtet, Vault-Remote konfiguriert",
        "autopush_noremote": "Stop-Hook verdrahtet, aber der Vault hat KEIN git-Remote — nichts kann gepusht werden",
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


# 1) recall hooks firing (fire-log fresh) — WARN (never FAIL) on a fresh install.
#    Miss records (type != "hit": zero/timeout/error/no_qmd) are counted separately —
#    they are searches that surfaced nothing, not recalls.
fire = os.path.join(PO, "lesson-fires.jsonl")
if os.path.exists(fire):
    total = d7 = 0
    miss7 = {"zero": 0, "timeout": 0, "error": 0, "no_qmd": 0}
    for line in open(fire, encoding="utf-8", errors="replace"):
        if not line.strip():
            continue
        try:
            r = json.loads(line)
            recent = (NOW - dt.datetime.fromisoformat(r.get("ts", ""))).days <= 7
        except Exception:
            continue
        typ = r.get("type", "hit")
        if typ == "hit":
            total += 1
            if recent:
                d7 += 1
        elif recent and typ in miss7:
            miss7[typ] += 1
    add("PASS" if d7 else "WARN", t("recall"),
        t("recall_7d").format(d7, total) if d7 else t("recall_stale"))
    searched = d7 + miss7["zero"]
    hard_misses = miss7["timeout"] + miss7["error"] + miss7["no_qmd"]
    if searched + hard_misses:
        st = "WARN" if hard_misses > max(3, (searched + hard_misses) // 5) else "PASS"
        add(st, t("misses"),
            t("misses_x").format(miss7["zero"], miss7["timeout"],
                                 miss7["error"] + miss7["no_qmd"])
            + (t("misses_hint") if st == "WARN" else ""))
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

# 10) inbox drafts reviewed (dreams/ + refs/ have their own checks below — don't nag twice)
inbox = [p for p in glob.glob(os.path.join(VAULT, "_inbox", "**", "*.md"), recursive=True)
         if os.sep + "dreams" + os.sep not in p and os.sep + "refs" + os.sep not in p]
add("PASS" if not inbox else "WARN", t("inbox"),
    t("inbox_none") if not inbox else t("inbox_n").format(len(inbox)))

# 11) nightly job steps from health.json — the formerly silent per-step failures
try:
    hj = json.load(open(os.path.join(PO, "health.json"), encoding="utf-8"))
    for jname, j in sorted((hj.get("jobs") or {}).items()):
        bad = [s["name"] for s in j.get("steps", []) if s.get("rc")]
        if bad:
            add("WARN", t("steps").format(jname),
                t("steps_fail").format(", ".join(bad[:4])
                                       + (" (+{})".format(len(bad) - 4) if len(bad) > 4 else "")))
        elif j.get("steps"):
            add("PASS", t("steps").format(jname), t("steps_ok").format(len(j["steps"])))
except Exception:
    add("INFO", t("steps").format("-"), t("steps_none"))

# 12) refs queue below the backpressure threshold (only meaningful if the dir exists)
refs = [p for p in glob.glob(os.path.join(VAULT, "_inbox", "refs", "*.md"))
        if not os.path.basename(p).startswith(("_INDEX", "_DIGEST"))]
add("PASS" if len(refs) <= 150 else "WARN", t("refs"),
    t("refs_n").format(len(refs)) if len(refs) <= 150 else t("refs_over").format(len(refs)))

# 13) chat-mining backlog (imported but never distilled — invisible backlogs stall silently)
def _mining_backlog(sub, state_file):
    try:
        mined = sum(1 for l in open(os.path.join(VAULT, state_file),
                                    encoding="utf-8", errors="replace") if l.strip())
    except Exception:
        mined = 0
    return max(0, len(glob.glob(os.path.join(VAULT, "chats", sub, "*.md"))) - mined)

n_chats = len(glob.glob(os.path.join(VAULT, "chats", "*", "*.md")))
if n_chats == 0:
    add("INFO", t("mining"), t("mining_none"))
else:
    backlog = _mining_backlog("code", ".chat_mining_state.txt") \
        + _mining_backlog("gpt", ".chatgpt_mining_state.txt")
    add("PASS" if backlog <= 30 else "WARN", t("mining"),
        t("mining_n").format(backlog) if backlog <= 30 else t("mining_over").format(backlog))

# 14) dreaming ran — optional, INFO if never configured or intentionally off, never FAIL
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

# 15) unreviewed dream notes (status: draft) — only if dreaming produced any
dream_drafts = 0
for p in glob.glob(os.path.join(VAULT, "_inbox", "dreams", "*.md")):
    try:
        if "status: draft" in open(p, encoding="utf-8", errors="replace").read(400):
            dream_drafts += 1
    except Exception:
        pass
if glob.glob(os.path.join(VAULT, "_inbox", "dreams", "*.md")):
    add("PASS" if dream_drafts <= 7 else "WARN", t("dreamnotes"),
        t("dreamnotes_n").format(dream_drafts) if dream_drafts <= 7
        else t("dreamnotes_over").format(dream_drafts))

# 16) vault autopush (opt-in): Stop hook wired -> the vault needs a git remote
try:
    sblob = open(os.path.join(CLAUDE_DIR, "settings.json"), encoding="utf-8").read()
except Exception:
    sblob = ""
if "vault_autopush.sh" in sblob:
    try:
        remotes = subprocess.run(["git", "-C", VAULT, "remote"],
                                 capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        remotes = ""
    add("PASS" if remotes else "WARN", t("autopush"),
        t("autopush_ok") if remotes else t("autopush_noremote"))
else:
    add("INFO", t("autopush"), t("autopush_off"))

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

# Mirror the verdict into health.json (a FAIL triggers the once-per-day notification
# there). Fail-open: a missing pos_health must never break the doctor itself.
try:
    if SCRIPTS_DIR not in sys.path:
        sys.path.insert(0, SCRIPTS_DIR)
    import pos_health
    pos_health.cmd_doctor_record(verdict, str(len(fails)), str(len(warns)), str(len(oks)))
except Exception:
    pass

sys.exit(1 if fails else 0)
