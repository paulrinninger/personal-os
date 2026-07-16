#!/usr/bin/env python3
"""dream.py — nightly consolidation for the Personal OS vault ("dreaming").

The idea: after the graph rebuild indexes the day's changes, a short local-LLM pass
runs like a mind consolidating memory overnight — condensing the day's residue,
surfacing connections between notes that never link to each other, spotting lesson
patterns, and ranking the review inbox — then writes ONE proposal note. Nothing here
ever edits a live note directly; every output is a suggestion with a checkbox, reviewed
via `/dream review`. $0, fully local: qmd (embeddings/search) does the semantic lifting
for free, and only one pass (residue) touches an LLM at all, capped at a handful of calls.

Passes (each writes its own state file under the day's work dir, so a killed run
resumes cleanly instead of redoing finished passes):
  fires        firing patterns from the recall hook's fire-log (no model)
  gc-digest    pre-chews lesson merge/cross-link candidates via os_lessons.py gc --json
               (nomic-embed-text, same engine /lessons-gc already uses)
  connections  new [[wikilink]] suggestions between recently-changed notes that don't
               already reference each other (qmd vsearch, embeddings only — no LLM)
  residue      "what happened yesterday" digest from session logs + newly imported
               chats (THE ONLY LLM pass: small local model, hard-capped call count)
  triage       ranks your review-inbox drafts against your active project hubs so you
               know which ones to look at first (nomic-embed-text, no LLM)
  ventures     checks brand-new project hubs against your own past done/parked ventures
               for a shared "shape" (embeddings + a transitive similarity check to avoid
               false positives; optional single LLM call to phrase the verdict — a rare,
               high-signal pass, capped at one pattern per night)
  producer     renders cold-outreach drafts from a queue you fill in yourself (pure
               templating, NO LLM — lead pain-points can't be invented) -> real Gmail
               drafts are only ever created by `/producer review`, never by this script
  report       assembles whichever passes produced something into the dream note

Config (env, all optional):
  PERSONAL_OS_VAULT         vault location                (default ~/vault)
  PERSONAL_OS_HOME          engine dir: fire-log, dream state, os_lessons.py
                                                            (default ~/.claude/personal-os)
  PERSONAL_OS_OLLAMA        ollama base URL                (default http://localhost:11434)
  PERSONAL_OS_EMBED_MODEL   embedding model                (default nomic-embed-text)
  PERSONAL_OS_DREAM_MODEL   generation model for the residue pass (default llama3.2:3b —
                            a small model is deliberate; this runs unattended overnight)

Usage: dream.py <fires|gc-digest|connections|residue|triage|report> [--date YYYY-MM-DD] [--force]
Typically driven by dream_run.sh (RAM pre-flight, kill switch, one pass per invocation).
"""
from __future__ import annotations
import argparse, datetime as dt, glob, json, math, os, re, shutil, subprocess, sys, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pos_utils
import qmd_search

VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
PO = os.path.expanduser(os.environ.get("PERSONAL_OS_HOME", os.path.join(
    os.path.expanduser(os.environ.get("PERSONAL_OS_CLAUDE_DIR", "~/.claude")), "personal-os")))
WORK_ROOT = os.path.join(PO, "dream-work")
DREAM_WORK_RETENTION_DAYS = 7  # short window: holds real lead names / venture-verdict text
CURSOR_FILE = os.path.join(PO, "dream-cursor.json")
FEEDBACK_FILE = os.path.join(PO, "dream-feedback.jsonl")
EMBED_CACHE = os.path.join(PO, "dream-embeds.json")
VENTURES_CURSOR = os.path.join(PO, "ventures-cursor.json")
VENTURES_EMBEDS = os.path.join(PO, "ventures-embeds.json")
PRODUCER_QUEUE = os.path.join(PO, "producer-queue.jsonl")
PRODUCER_TEMPLATES = os.path.join(PO, "producer-templates.json")
PRODUCER_FEEDBACK_FILE = os.path.join(PO, "producer-feedback.jsonl")
PRODUCER_DRAFTS_DIR = os.path.join(VAULT, "_inbox", "producer-drafts")
FIRE_LOG = os.path.join(PO, "lesson-fires.jsonl")
OS_LESSONS = os.path.join(PO, "os_lessons.py")
DREAMS_DIR = os.path.join(VAULT, "_inbox", "dreams")

OLLAMA_BASE = os.environ.get("PERSONAL_OS_OLLAMA", "http://localhost:11434")
OLLAMA_GEN = OLLAMA_BASE + "/api/generate"
OLLAMA_EMBED = OLLAMA_BASE + "/api/embeddings"
OLLAMA_VERSION = OLLAMA_BASE + "/api/version"
GEN_MODEL = os.environ.get("PERSONAL_OS_DREAM_MODEL", "llama3.2:3b")
EMBED_MODEL = os.environ.get("PERSONAL_OS_EMBED_MODEL", "nomic-embed-text")

# Baseline params; nudged over time by acceptance feedback from `/dream review` (see
# adaptive_params). Deliberately conservative caps — a dream note should be a two-minute
# read, not a second inbox.
DEFAULTS = {
    "fires":       {"cap": 5},
    "gc":          {"cap": 5},
    "connections": {"cap": 8, "threshold": 75, "max_notes": 30},
    "residue":     {"max_docs": 10, "max_bullets": 6, "call_timeout": 120},
    "triage":      {"cap": 10, "max_new_embeds": 120},
    "ventures":    {"threshold": 78, "min_siblings": 2, "sibling_threshold": 75, "cap": 1},
    "producer":    {"cap": 5},
}
# Calibrate `threshold` against your own vault before relying on it: embed a few known
# "same shape, different outcome" project pairs (nomic-embed-text via ollama_embed) and
# see where the true-match band sits vs. an unrelated control pair — cosine scores for
# German/English business prose can land anywhere in the 70s-80s depending on your writing
# style. VENTURES_MIN_THRESHOLD below is a hard floor so adaptive_params never drifts it
# into the noise band even after a run of "accepted" feedback.
VENTURES_MIN_THRESHOLD = 75


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def today(args) -> str:
    return args.date or dt.date.today().isoformat()


def workdir(args) -> str:
    d = os.path.join(WORK_ROOT, today(args))
    # owner-only: this now holds producer lead names / ventures verdict text (added this
    # round), not just low-sensitivity pass counters like before — mode= only applies at
    # creation time, so this hardens new date-folders going forward, not existing ones.
    os.makedirs(d, mode=0o700, exist_ok=True)
    return d


def prune_dream_work(days: int = DREAM_WORK_RETENTION_DAYS) -> None:
    # real wall-clock age, not the possibly-overridden --date, so a manual backfill run
    # never keeps stale lead/verdict data around longer than the retention window.
    cutoff = dt.date.today() - dt.timedelta(days=days)
    if not os.path.isdir(WORK_ROOT):
        return
    for name in sorted(os.listdir(WORK_ROOT)):
        path = os.path.join(WORK_ROOT, name)
        if not os.path.isdir(path):
            continue
        try:
            folder_date = dt.date.fromisoformat(name)
        except ValueError:
            continue
        if folder_date < cutoff:
            shutil.rmtree(path)
            log(f"[prune] dream-work/{name} removed (older than {days}d)")


def pass_done(args, name: str) -> bool:
    if args.force:
        return False
    path = os.path.join(workdir(args), name + ".json")
    if not os.path.exists(path):
        return False
    try:
        json.load(open(path, encoding="utf-8"))
        return True
    except Exception:
        return False  # torn file from an interrupted run -- treat as not-done, retry


def write_pass(args, name: str, data: dict):
    data["_pass"] = name
    data["_ts"] = dt.datetime.now().isoformat(timespec="seconds")
    path = os.path.join(workdir(args), name + ".json")
    # atomic tmp+replace write (shared pos_utils implementation) — without it, the
    # orchestrator's timeout can SIGTERM mid-json.dump and leave a torn file that
    # pass_done() would otherwise misread as "done".
    pos_utils.write_atomic(path, data)
    log(f"[{name}] wrote {path}")


def adaptive_params(pass_name: str) -> dict:
    """Feedback-adaptive (counters only, no ML): acceptance rate over the last 20
    suggestions shown for this pass. <25% -> stricter (threshold +2 / cap -2); >60% ->
    looser (threshold floor 78 / cap +2)."""
    p = dict(DEFAULTS[pass_name])
    verdicts = []
    # /producer review deliberately writes to its OWN channel (producer-feedback.jsonl,
    # see claude/commands/producer.md) instead of dream-feedback.jsonl, so accepted/
    # rejected drafts don't skew the other passes' thresholds. Without this branch,
    # adaptive_params("producer") would read the wrong (empty) file and your feedback
    # from /producer review would never have any effect.
    feedback_file = PRODUCER_FEEDBACK_FILE if pass_name == "producer" else FEEDBACK_FILE
    if os.path.exists(feedback_file):
        for line in open(feedback_file, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("pass") == pass_name and r.get("verdict") in ("accepted", "rejected"):
                verdicts.append(r["verdict"])
    recent = verdicts[-20:]
    if len(recent) >= 8:
        acc = recent.count("accepted") / len(recent)
        if acc < 0.25:
            if "threshold" in p:
                p["threshold"] = min(p["threshold"] + 2, 92)
            p["cap"] = max(p.get("cap", 5) - 2, 2)
        elif acc > 0.60:
            if "threshold" in p:
                p["threshold"] = max(p["threshold"] - 2, 78)
            p["cap"] = min(p.get("cap", 5) + 2, 12)
        p["_acceptance"] = round(acc, 2)
    return p


def ollama_up() -> bool:
    try:
        with urllib.request.urlopen(OLLAMA_VERSION, timeout=2):
            return True
    except Exception:
        return False


def ollama_generate(prompt: str, timeout: int = 120) -> str:
    payload = json.dumps({
        "model": GEN_MODEL, "prompt": prompt, "stream": False,
        # Short-lived keep_alive, not 0: the residue pass makes several calls back to
        # back, and reloading the model fresh each time would just thrash. dream_run.sh
        # unloads it explicitly at the end of the run.
        "keep_alive": "2m",
        "options": {"num_ctx": 4096, "temperature": 0.2},
    }).encode()
    req = urllib.request.Request(OLLAMA_GEN, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return (json.load(resp).get("response") or "").strip()


def ollama_embed(text: str, timeout: int = 30) -> list[float]:
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text[:4000],
                          "keep_alive": "5m"}).encode()
    req = urllib.request.Request(OLLAMA_EMBED, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.load(resp).get("embedding", [])


def cosine(a, b) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def read_note(path: str, max_chars: int = 4000) -> tuple[str, str]:
    """(title, body-without-frontmatter)"""
    try:
        t = open(path, encoding="utf-8", errors="replace").read(max_chars * 2)
    except Exception:
        return os.path.basename(path)[:-3], ""
    title = None
    body = t
    if t.startswith("---"):
        end = t.find("\n---", 3)
        if end > 0:
            fm, body = t[:end], t[end + 4:]
            m = re.search(r"^title:\s*(.+)$", fm, re.M)
            if m:
                title = m.group(1).strip().strip('"')
    return title or os.path.basename(path)[:-3], body.strip()[:max_chars]


def wikilinks_of(path: str) -> set[str]:
    try:
        t = open(path, encoding="utf-8", errors="replace").read()
    except Exception:
        return set()
    return {w.split("|")[0].strip().lower() for w in re.findall(r"\[\[([^\]]+)\]\]", t)}


# ---------------------------------------------------------------- pass: fires
STOPWORDS = set("""the and for with this that from https echo grep head tail sort file
claude users home local private your please could would should""".split())


def cmd_fires(args):
    if pass_done(args, "fires"):
        return log("[fires] already done (resume) — skip")
    p = adaptive_params("fires")
    now = dt.datetime.now()
    per_lesson, triggers, words = {}, {}, {}
    total7 = 0
    if os.path.exists(FIRE_LOG):
        for line in open(FIRE_LOG, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
                ts = dt.datetime.fromisoformat(r.get("ts", ""))
            except Exception:
                continue
            if (now - ts).days > 7:
                continue
            # miss records (type: zero/timeout/error/no_qmd) do not count as recalls
            if r.get("type", "hit") != "hit":
                continue
            total7 += 1
            path = r.get("path", "?")
            a = per_lesson.setdefault(path, {"count": 0, "max_score": 0})
            a["count"] += 1
            a["max_score"] = max(a["max_score"], r.get("score", 0))
            trg = r.get("trigger", "?")
            triggers[trg] = triggers.get(trg, 0) + 1
            if trg == "UserPromptSubmit":
                for w in re.findall(r"[a-zA-Z-]{5,}", (r.get("prompt") or "").lower()):
                    if w not in STOPWORDS:
                        words[w] = words.get(w, 0) + 1
    top = sorted(per_lesson.items(), key=lambda kv: -kv[1]["count"])[:p["cap"]]
    hot = [{"path": k, "count": v["count"], "max_score": v["max_score"]}
           for k, v in per_lesson.items() if v["count"] >= 3 and v["max_score"] >= 65]
    hot.sort(key=lambda h: -h["count"])
    # The hooks also log misses (type: zero/timeout/error/no_qmd) — a 7-day count
    # for the report makes coverage gaps and cold-start timeouts visible.
    misses = {"zero": 0, "timeout": 0, "error": 0, "no_qmd": 0}
    if os.path.exists(FIRE_LOG):
        for line in open(FIRE_LOG, encoding="utf-8", errors="replace"):
            try:
                r = json.loads(line)
                if (now - dt.datetime.fromisoformat(r.get("ts", ""))).days > 7:
                    continue
            except Exception:
                continue
            typ = r.get("type", "hit")
            if typ in misses:
                misses[typ] += 1
    write_pass(args, "fires", {
        "params": p, "total_fires_7d": total7,
        "misses_7d": {k: v for k, v in misses.items() if v},
        "top_firers": [{"path": k, "count": v["count"]} for k, v in top],
        "hot_lessons": hot[:p["cap"]],
        "trigger_mix": triggers,
        "hot_topics": sorted(words.items(), key=lambda kv: -kv[1])[:5],
    })


# ------------------------------------------------------------- pass: gc-digest
def cmd_gc_digest(args):
    if pass_done(args, "gc"):
        return log("[gc] already done (resume) — skip")
    if not ollama_up():
        return write_pass(args, "gc", {"skipped": "ollama not reachable"})
    if not os.path.exists(OS_LESSONS):
        return write_pass(args, "gc", {"skipped": "os_lessons.py not found — install incomplete?"})
    p = adaptive_params("gc")
    try:
        out = subprocess.run([sys.executable, OS_LESSONS, "gc", "--json"],
                             capture_output=True, text=True, timeout=280)
        data = json.loads(out.stdout)
    except Exception as e:
        return write_pass(args, "gc", {"error": f"os_lessons gc failed: {e}"})
    write_pass(args, "gc", {
        "params": p,
        "merge_pairs": data.get("merge_pairs", [])[:p["cap"]],
        "related_pairs": data.get("related_pairs", [])[:p["cap"]],
        "cold_count": len(data.get("cold", [])),
        "stale_count": len(data.get("stale", [])),
        "total": data.get("total"),
    })


# ---------------------------------------------------------- pass: connections
def qmd_vsearch(query: str, n: int = 5, timeout: int = 45) -> list[dict]:
    """Thin adapter over the shared client qmd_search.vsearch (JSON mode).

    Replaces the fourth divergent hand-rolled parser — the old `Score: N%` regex
    would have silently scored everything 0 on %-less qmd output (no suggestions,
    no error)."""
    res = qmd_search.vsearch(query, n=n, timeout=timeout)
    if res["outcome"] != "ok":
        log(f"[qmd] WARN: vsearch {res['outcome']}: {res['error']}")
        return []
    hits = []
    for h in res["hits"]:
        parts = h["path"].split("/", 1)
        hits.append({
            "collection": parts[0] if len(parts) > 1 else "",
            "relpath": parts[1] if len(parts) > 1 else h["path"],
            "path": h["abs_path"],
            "score": h["score"],
            "snippet": h["snippet"][:180],
        })
    return hits


def cmd_connections(args):
    if pass_done(args, "connections"):
        return log("[connections] already done (resume) — skip")
    p = adaptive_params("connections")
    cutoff = dt.datetime.now().timestamp() - 7 * 86400
    cand = []
    for sub in ("lessons", "knowledge", "ideas", "projects", "permanent", "profile"):
        for f in glob.glob(os.path.join(VAULT, sub, "**", "*.md"), recursive=True):
            try:
                mt = os.path.getmtime(f)
            except OSError:
                continue
            if mt >= cutoff:
                cand.append((mt, f))
    cand.sort(reverse=True)
    cand = [f for _, f in cand[:p["max_notes"]]]
    suggestions, seen_pairs = [], set()
    for src in cand:
        title, body = read_note(src, 300)
        for hit in qmd_vsearch(f"{title} {body[:300]}", n=5):
            tgt = hit.get("path")
            if not tgt or not os.path.exists(tgt):
                continue
            try:
                if os.path.samefile(tgt, src):
                    continue
            except OSError:
                continue
            if hit["score"] < p["threshold"]:
                continue
            a_stem = os.path.basename(src)[:-3].lower()
            b_stem = os.path.basename(tgt)[:-3].lower()
            key = tuple(sorted((a_stem, b_stem)))
            if key in seen_pairs:
                continue
            # an existing link in EITHER direction already covers this suggestion
            if b_stem in wikilinks_of(src) or a_stem in wikilinks_of(tgt):
                continue
            seen_pairs.add(key)
            suggestions.append({"a": os.path.relpath(src, VAULT), "b": os.path.relpath(tgt, VAULT),
                                "score": hit["score"], "snippet": hit["snippet"]})
    suggestions.sort(key=lambda s: -s["score"])
    write_pass(args, "connections", {
        "params": p, "notes_scanned": len(cand),
        "suggestions": suggestions[:p["cap"]],
    })


# ------------------------------------------------------------------- pass: residue
def _yesterday_docs(args, cap: int) -> tuple[list[str], float]:
    y = (dt.date.fromisoformat(today(args)) - dt.timedelta(days=1)).isoformat()
    docs = list(glob.glob(os.path.join(VAULT, "**", "logs", f"{y}-*.md"), recursive=True))
    docs.extend(glob.glob(os.path.join(VAULT, "logs", f"{y}-*.md")))
    cursor = {}
    try:
        cursor = json.load(open(CURSOR_FILE))
    except Exception:
        pass
    last = cursor.get("chats_mtime", dt.datetime.now().timestamp() - 86400)
    chats = []
    for f in glob.glob(os.path.join(VAULT, "chats", "*", "*.md")):
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        if mt > last:
            chats.append((mt, f))
    # FIFO (oldest first) + advance the cursor ONLY over the slice actually consumed.
    # Previously: sort(reverse) + cursor = max over ALL — everything beyond `room`
    # was skipped permanently (backlog chats silently vanished from dreaming).
    chats.sort()
    docs = list(dict.fromkeys(docs))[:cap]
    room = max(0, cap - len(docs))
    taken = chats[:room]
    docs += [f for _, f in taken]
    return docs, (max(m for m, _ in taken) if taken else last)


def cmd_residue(args):
    if pass_done(args, "residue"):
        return log("[residue] already done (resume) — skip")
    if not ollama_up():
        return write_pass(args, "residue", {"skipped": "ollama not reachable"})
    p = adaptive_params("residue")
    docs, new_cursor = _yesterday_docs(args, p["max_docs"])
    git_summary = ""
    try:
        git_summary = subprocess.run(
            ["git", "-C", VAULT, "log", "--since=36 hours ago", "--oneline", "--stat"],
            capture_output=True, text=True, timeout=20).stdout[:2000]
    except Exception:
        pass
    calls = 0
    doc_bullets = []
    for f in docs:
        title, body = read_note(f, 6000)
        if not body:
            continue
        try:
            resp = ollama_generate(
                "Summarize this note from a personal knowledge vault in 2-3 bullets: "
                "what happened / was decided, and what was left open? Be concrete and "
                "specific (names, numbers, projects) — no filler phrases. Bullets only, "
                "no preamble.\n\nTITLE: " + title + "\n\n" + body,
                timeout=p["call_timeout"])
            calls += 1
            if resp:
                doc_bullets.append({"doc": os.path.relpath(f, VAULT), "bullets": resp[:800]})
        except Exception as e:
            log(f"[residue] WARN: LLM call failed for {f}: {e}")
        if calls >= p["max_docs"]:
            break
    synthesis = ""
    if doc_bullets or git_summary:
        try:
            material = "\n\n".join(f"## {d['doc']}\n{d['bullets']}" for d in doc_bullets)
            synthesis = ollama_generate(
                f"You are the nightly dreaming pass for a personal knowledge vault. Condense "
                f"yesterday into at most {p['max_bullets']} bullets (what happened, what was "
                "left open) plus EXACTLY one bullet 'Suggestion for today: …'. Be concrete, "
                "don't invent anything not in the material. Bullets only, no preamble.\n\n"
                "SESSION DIGESTS:\n" + material[:8000] +
                "\n\nVAULT GIT ACTIVITY (36h):\n" + git_summary,
                timeout=p["call_timeout"])
            calls += 1
        except Exception as e:
            log(f"[residue] WARN: synthesis failed: {e}")
    write_pass(args, "residue", {
        "params": p, "docs": [d["doc"] for d in doc_bullets],
        "llm_calls": calls, "synthesis": synthesis,
    })
    # Only advance the cursor after a successful pass (resume safety).
    try:
        cursor = {}
        if os.path.exists(CURSOR_FILE):
            cursor = json.load(open(CURSOR_FILE))
        cursor["chats_mtime"] = new_cursor
        pos_utils.write_atomic(CURSOR_FILE, cursor)
    except Exception as e:
        log(f"[residue] WARN: cursor not updated: {e}")


# -------------------------------------------------------------------- pass: triage
def cmd_triage(args):
    if pass_done(args, "triage"):
        return log("[triage] already done (resume) — skip")
    if not ollama_up():
        return write_pass(args, "triage", {"skipped": "ollama not reachable"})
    p = adaptive_params("triage")
    hubs = []
    for f in glob.glob(os.path.join(VAULT, "projects", "*.md")):
        try:
            t = open(f, encoding="utf-8", errors="replace").read(3000)
        except Exception:
            continue
        if re.search(r"^status:\s*active", t, re.M):
            title, body = read_note(f, 800)
            try:
                hubs.append({"name": os.path.basename(f)[:-3],
                             "vec": ollama_embed(title + " " + body)})
            except Exception:
                pass
    if not hubs:
        return write_pass(args, "triage", {"skipped": "no active project hubs to embed"})
    cache = {}
    try:
        cache = json.load(open(EMBED_CACHE))
    except Exception:
        pass
    # Whatever is sitting in the review inbox (harvest drafts: lessons/, ideas/<kind>/, …)
    cards = sorted(glob.glob(os.path.join(VAULT, "_inbox", "**", "*.md"), recursive=True))
    new_embeds, dropped = 0, 0
    scored = []
    for f in cards:
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        ent = cache.get(f)
        if not ent or ent.get("mtime") != mt:
            if new_embeds >= p["max_new_embeds"]:
                dropped += 1   # no silent cap — this shows up in the report
                continue
            title, body = read_note(f, 1200)
            try:
                cache[f] = {"mtime": mt, "vec": ollama_embed(title + " " + body)}
                new_embeds += 1
            except Exception:
                continue
        vec = cache[f]["vec"]
        best = max(((cosine(vec, h["vec"]), h["name"]) for h in hubs), default=(0, "?"))
        scored.append({"card": os.path.relpath(f, VAULT), "hub": best[1],
                       "score": round(best[0], 3)})
    pos_utils.write_atomic(EMBED_CACHE, cache)
    scored.sort(key=lambda s: -s["score"])
    write_pass(args, "triage", {
        "params": p, "cards_total": len(cards), "new_embeds": new_embeds,
        "embeds_deferred": dropped,
        "top": scored[:p["cap"]],
    })


# ----------------------------------------------------------------- pass: ventures
def _hub_meta(path: str) -> dict:
    """Reads status/created/domain from a project hub's frontmatter (raw scan — these
    are always single-line scalars in this format, no YAML parser needed)."""
    try:
        t = open(path, encoding="utf-8", errors="replace").read(2000)
    except Exception:
        return {}
    meta = {}
    for key in ("status", "created", "domain"):
        m = re.search(rf"^{key}:\s*(.+)$", t, re.M)
        if m:
            meta[key] = m.group(1).strip().strip('"')
    return meta


def _stand_first_line(path: str) -> str:
    """First non-empty line under a '## Status' (or '## Stand') heading — hubs following
    the vault-scaffold template usually write '<status> — <short reason>' there."""
    try:
        t = open(path, encoding="utf-8", errors="replace").read(4000)
    except Exception:
        return ""
    m = re.search(r"^## (?:Status|Stand)\s*\n+(.+)$", t, re.M)
    return m.group(1).strip()[:220] if m else ""


def _ventures_embed_of(cache: dict, path: str, mtime: float) -> list[float] | None:
    ent = cache.get(path)
    if ent and ent.get("mtime") == mtime:
        return ent["vec"]
    title, body = read_note(path, 600)  # just the opening "what this is" paragraph
    try:
        vec = ollama_embed(title + " " + body)
    except Exception:
        return None
    cache[path] = {"mtime": mtime, "vec": vec}
    return vec


def cmd_ventures(args):
    if pass_done(args, "ventures"):
        return log("[ventures] already done (resume) — skip")
    p = adaptive_params("ventures")
    threshold = max(p.get("threshold", 78), VENTURES_MIN_THRESHOLD)
    min_sib = p.get("min_siblings", 2)
    sib_threshold = p.get("sibling_threshold", 75)

    cursor = {}
    try:
        cursor = json.load(open(VENTURES_CURSOR))
    except Exception:
        pass
    now = dt.datetime.now()
    hubs = sorted(glob.glob(os.path.join(VAULT, "projects", "*.md")))
    if not hubs:
        return write_pass(args, "ventures", {"skipped": "no project hubs"})

    candidates = []  # (path, mtime, meta) — new/changed AND young enough to be "a new project"
    for path in hubs:
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        if cursor.get(path) == mt:
            continue  # unchanged since last check
        meta = _hub_meta(path)
        try:
            age_days = (now - dt.datetime.fromisoformat(meta.get("created", "1970-01-01"))).days
        except Exception:
            age_days = 9999
        if age_days <= 21:
            candidates.append((path, mt, meta))

    if not candidates:
        return write_pass(args, "ventures", {"skipped": "no new hub in the 21-day window"})
    if not ollama_up():
        return write_pass(args, "ventures", {"skipped": "ollama not reachable"})

    cache = {}
    try:
        cache = json.load(open(VENTURES_EMBEDS))
    except Exception:
        pass

    # Comparison pool: done/parked hubs only — never active. An active project shouldn't
    # see itself as one of its own "dead siblings".
    siblings_pool = []
    for path in hubs:
        meta = _hub_meta(path)
        if meta.get("status") not in ("done", "parked"):
            continue
        try:
            mt = os.path.getmtime(path)
        except OSError:
            continue
        vec = _ventures_embed_of(cache, path, mt)
        if vec:
            siblings_pool.append({"path": path, "vec": vec})

    patterns = []
    evaluated = []  # (path, mt) ACTUALLY evaluated — cursor may only advance for these,
                    # never for candidates the cap-triggered break never reached (else
                    # they'd be marked "checked" forever without ever being checked)
    for path, mt, meta in candidates:
        evaluated.append((path, mt))
        vec = _ventures_embed_of(cache, path, mt)
        if not vec:
            continue
        scored = sorted(
            ((cosine(vec, s["vec"]), s) for s in siblings_pool if s["path"] != path),
            key=lambda x: -x[0])
        matches = [(score, s) for score, s in scored if score * 100 >= threshold]
        if len(matches) < min_sib:
            continue
        # Transitive brake: try EVERY match as a potential cluster seed, not just
        # matches[0] — otherwise a real pair among matches[1:] that's mutually similar
        # but doesn't happen to match the top-scored candidate would be missed entirely.
        cluster = None
        for i in range(len(matches)):
            cand_cluster = [matches[i]]
            for j, (score, s) in enumerate(matches):
                if j == i:
                    continue
                if all(cosine(s["vec"], m[1]["vec"]) * 100 >= sib_threshold for m in cand_cluster):
                    cand_cluster.append((score, s))
                if len(cand_cluster) >= min_sib:
                    break
            if len(cand_cluster) >= min_sib:
                cluster = cand_cluster
                break
        if not cluster:
            continue
        sib_paths = [s["path"] for _, s in cluster]
        stand_lines = [f"[[{os.path.basename(sp)[:-3]}]]: {_stand_first_line(sp)}" for sp in sib_paths]
        verdict = " / ".join(_stand_first_line(sp) for sp in sib_paths if _stand_first_line(sp))
        if ollama_up():
            try:
                verdict = ollama_generate(
                    "These past projects seem to share a shape with a new project. Condense "
                    "into EXACTLY one short sentence (max 25 words) what they had in common "
                    "and why they didn't work out — ONLY from the material given, don't invent "
                    "or speculate. Just the one sentence, no preamble.\n\n"
                    + "\n".join(stand_lines),
                    timeout=60).strip() or verdict
            except Exception as e:
                log(f"[ventures] WARN: synthesis failed, using raw text: {e}")
        patterns.append({
            "new_hub": os.path.basename(path)[:-3],
            "siblings": [os.path.basename(sp)[:-3] for sp in sib_paths],
            "score": round(cluster[0][0] * 100, 1),
            "verdict": (verdict if len(verdict) <= 300 else verdict[:300].rsplit(" ", 1)[0] + "…"),
        })
        if len(patterns) >= p.get("cap", 1):
            break

    for path, mt in evaluated:  # only for candidates actually evaluated above, not all candidates
        cursor[path] = mt
    pos_utils.write_atomic(VENTURES_CURSOR, cursor)
    pos_utils.write_atomic(VENTURES_EMBEDS, cache)

    write_pass(args, "ventures", {"params": p, "candidates_checked": len(candidates), "patterns": patterns})


# ----------------------------------------------------------------- pass: producer
def cmd_producer(args):
    if pass_done(args, "producer"):
        return log("[producer] already done (resume) — skip")
    p = adaptive_params("producer")
    if not os.path.exists(PRODUCER_QUEUE):
        return write_pass(args, "producer", {"skipped": "no queue file (producer-queue.jsonl missing)"})
    try:
        templates = json.load(open(PRODUCER_TEMPLATES))
    except Exception as e:
        return write_pass(args, "producer", {"error": f"producer-templates.json unreadable: {e}"})

    entries = []
    with open(PRODUCER_QUEUE, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                try:
                    entries.append(json.loads(line))
                except Exception:
                    continue

    def complete(e):
        # id is required too, not just observation/pain_point — the queue-drain step
        # below dedupes rendered entries BY id, so an id-less entry could never be
        # safely removed from the queue after rendering (and two id-less entries would
        # collide on the same draft filename, `{date}-x.md`).
        lead = e.get("lead", {})
        # These two fields MUST come from you — a model has no basis to invent a real
        # lead's pain point, and doing so is exactly the failure mode this pass exists
        # to avoid. Missing either -> skipped, never silently generated.
        return bool(e.get("id")) and bool(lead.get("observation")) and bool(lead.get("pain_point"))

    incomplete = [e for e in entries if not complete(e)]
    complete_entries = [e for e in entries if complete(e)]
    valid = complete_entries[:p["cap"]]

    os.makedirs(PRODUCER_DRAFTS_DIR, exist_ok=True)
    drafts = []
    rendered_ids = set()
    for e in valid:
        tmpl = templates.get(e.get("playbook", ""))
        if not tmpl:
            incomplete.append(e)
            continue
        lead = e["lead"]
        try:
            # Pure templating — NO ollama_generate. An LLM call here would only add
            # hallucination risk with no upside over the playbook sentences you already
            # wrote; observation/pain_point come verbatim from you.
            text = tmpl.format(**{**lead, "cta": e.get("cta", "")})
        except KeyError as ex:
            log(f"[producer] WARN: missing template variable for {e.get('id')}: {ex}")
            incomplete.append(e)
            continue
        fname = f"{today(args)}-{e.get('id', 'x')[:8]}.md"
        note = os.path.join(PRODUCER_DRAFTS_DIR, fname)
        with open(note, "w", encoding="utf-8") as f:
            f.write("\n".join([
                "---", f"title: Producer draft — {lead.get('company', '?')}",
                "tags: [producer, draft]", f"created: {today(args)}", "status: draft",
                "type: producer-draft", f"playbook: {e.get('playbook')}",
                f"lead_company: {lead.get('company', '?')}", "---", "",
                "> DRAFT ONLY — nothing has been sent. Review with: /producer review", "",
                text, "",
            ]))
        drafts.append({"id": e.get("id"), "lead_company": lead.get("company", "?"),
                       "playbook": e.get("playbook"), "file": note})
        rendered_ids.add(e["id"])

    # Drain the queue: keep only entries that were NOT successfully rendered this run
    # (incomplete, or complete but past tonight's cap) — otherwise every un-reviewed lead
    # would get re-rendered into a NEW, duplicate draft file every single night, since
    # nothing previously trimmed the queue after a successful render.
    remaining = [e for e in entries if e.get("id") not in rendered_ids]
    tmp = PRODUCER_QUEUE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        for e in remaining:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    os.replace(tmp, PRODUCER_QUEUE)

    write_pass(args, "producer", {
        "params": p, "drafts": drafts, "incomplete": len(incomplete),
        "queue_remaining": len(remaining),
    })


# ---------------------------------------------------------------------- report writer
def _load(args, name):
    try:
        return json.load(open(os.path.join(workdir(args), name + ".json")))
    except Exception:
        return {}


def cmd_report(args):
    d = today(args)
    did = d.replace("-", "")
    fires, gc = _load(args, "fires"), _load(args, "gc")
    conn, res, tri = _load(args, "connections"), _load(args, "residue"), _load(args, "triage")
    ven, prod = _load(args, "ventures"), _load(args, "producer")
    sec = []

    if res.get("synthesis"):
        sec.append(f"## Yesterday's residue ({len(res.get('docs', []))} documents)\n"
                   + res["synthesis"].strip())
    if conn.get("suggestions"):
        lines = [f"## New connections ({len(conn['suggestions'])})"]
        for i, s in enumerate(conn["suggestions"], 1):
            a = os.path.splitext(s['a'])[0]
            b = os.path.splitext(s['b'])[0]
            lines.append(f"- [ ] [[{a}]] <-> [[{b}]] — score {s['score']}"
                         + (f" — {s['snippet']}" if s.get("snippet") else "")
                         + f"  ^d{did}-b{i}")
        sec.append("\n".join(lines))
    if gc.get("merge_pairs") or gc.get("related_pairs"):
        lines = ["## Lessons to consolidate -> run /lessons-gc"]
        i = 0
        for pr in gc.get("merge_pairs", []):
            i += 1
            lines.append(f"- [ ] merge ({pr['cosine']}): [[{os.path.splitext(os.path.basename(pr['a']))[0]}]]"
                         f" + [[{os.path.splitext(os.path.basename(pr['b']))[0]}]]  ^d{did}-m{i}")
        for pr in gc.get("related_pairs", []):
            i += 1
            lines.append(f"- [ ] cross-link ({pr['cosine']}): [[{os.path.splitext(os.path.basename(pr['a']))[0]}]]"
                         f" <-> [[{os.path.splitext(os.path.basename(pr['b']))[0]}]]  ^d{did}-m{i}")
        if gc.get("cold_count") or gc.get("stale_count"):
            lines.append(f"- Also: {gc.get('cold_count', 0)} cold, {gc.get('stale_count', 0)} stale "
                         f"(of {gc.get('total', '?')}) — details via /lessons-gc")
        sec.append("\n".join(lines))
    if fires.get("top_firers") or fires.get("hot_topics"):
        lines = ["## Firing patterns (7 days)"]
        if fires.get("total_fires_7d"):
            trg = ", ".join(f"{k} {v}x" for k, v in sorted(fires.get("trigger_mix", {}).items(),
                                                           key=lambda kv: -kv[1]))
            lines.append(f"- {fires['total_fires_7d']} recalls ({trg})")
        for t in fires.get("top_firers", []):
            lines.append(f"- top: {t['count']}x [[{os.path.splitext(os.path.basename(t['path']))[0]}]]")
        for h in fires.get("hot_lessons", []):
            lines.append(f"- [ ] hot ({h['count']}x, score {h['max_score']}): "
                         f"[[{os.path.splitext(os.path.basename(h['path']))[0]}]] — sharpen the rule?  ^d{did}-f{h['count']}")
        if fires.get("hot_topics"):
            lines.append("- hot topics: " + ", ".join(w for w, _ in fires["hot_topics"]))
        sec.append("\n".join(lines))
    if tri.get("top"):
        lines = [f"## Inbox triage — review these first ({len(tri['top'])} of {tri.get('cards_total', '?')} drafts)"]
        for i, s in enumerate(tri["top"], 1):
            lines.append(f"- [ ] {s['card']} -> [[{s['hub']}]] ({s['score']})  ^d{did}-t{i}")
        if tri.get("embeds_deferred"):
            lines.append(f"- ({tri['embeds_deferred']} drafts not yet embedded — future nights)")
        sec.append("\n".join(lines))
    if ven.get("patterns"):
        lines = ["## Venture patterns detected — read before you start"]
        for i, pat in enumerate(ven["patterns"], 1):
            sibs = " / ".join(f"[[{s}]]" for s in pat["siblings"])
            lines.append(f"- [ ] [[{pat['new_hub']}]] resembles {sibs} (score {pat['score']}) — "
                        f"{pat['verdict']}  ^d{did}-v{i}")
        sec.append("\n".join(lines))
    if prod.get("error"):
        # without this branch, a corrupt producer-templates.json (e.g. interrupted mid-
        # edit) looks IDENTICAL in the report to "nothing in the queue tonight" — both
        # produce no 'drafts' key, so the whole section used to silently stay empty.
        sec.append(f"## Producer — error\n- {prod['error']} (queue was NOT modified)")
    elif prod.get("drafts"):
        lines = [f"## Producer drafts rendered ({len(prod['drafts'])}) -> /producer review"]
        for draft in prod["drafts"]:
            lines.append(f"- {draft['lead_company']} ({draft['playbook']})")
        if prod.get("incomplete"):
            # "incomplete" bundles 3 distinct causes (required field/id missing, unknown
            # playbook, missing template variable) — the text must not name just one of
            # them as THE cause, or it points at the wrong root cause for the other two.
            lines.append(f"- ({prod['incomplete']} queue entries incomplete/invalid — "
                         f"required field/id missing, unknown playbook, or missing template variable)")
        overflow = prod.get("queue_remaining", 0) - prod.get("incomplete", 0)
        if overflow > 0:
            lines.append(f"- ({overflow} more complete entries waiting — tonight's cap reached)")
        sec.append("\n".join(lines))

    if not sec:
        log("[report] a dreamless night — no note written")
        return
    passes = [nm for nm, dd in (("residue", res), ("connections", conn), ("fires", fires),
                                ("gc", gc), ("triage", tri), ("ventures", ven), ("producer", prod))
              if dd and not dd.get("skipped")]
    llm_calls = res.get("llm_calls", 0)
    os.makedirs(DREAMS_DIR, exist_ok=True)
    note = os.path.join(DREAMS_DIR, f"{d}-dream.md")
    body = "\n".join([
        "---",
        f"title: Dream {d}",
        "tags: [dream, personal-os]",
        f"created: {d}",
        f"updated: {d}",
        "status: draft",
        "type: dream",
        "---",
        "",
        f"# Dream — {d}",
        "> Suggestions only — nothing was changed. Review with `/dream review`. "
        "Disable overnight runs: create a file named `dream.off` in this engine's home dir.",
        "",
        "\n\n".join(sec),
        "",
        "---",
        f"_Run: {dt.datetime.now().strftime('%H:%M')} · passes: {' '.join(passes)} · "
        f"LLM calls: {llm_calls} · model: {GEN_MODEL}_",
        "",
    ])
    with open(note, "w", encoding="utf-8") as f:
        f.write(body)
    log(f"[report] dream note: {note} ({len(sec)} sections)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fires", "gc-digest", "connections", "residue",
                                    "triage", "ventures", "producer", "report"])
    ap.add_argument("--date", help="YYYY-MM-DD override (testing)")
    ap.add_argument("--force", action="store_true", help="recompute a pass even if resume-cached")
    args = ap.parse_args()
    os.makedirs(PO, exist_ok=True)
    prune_dream_work()
    {"fires": cmd_fires, "gc-digest": cmd_gc_digest, "connections": cmd_connections,
     "residue": cmd_residue, "triage": cmd_triage, "ventures": cmd_ventures,
     "producer": cmd_producer, "report": cmd_report}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
