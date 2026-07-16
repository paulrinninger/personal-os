#!/usr/bin/env python3
"""Personal-OS lesson health engine — Measure + Prune for the vault's lessons/.

Local & $0: reads lesson frontmatter + the recall hook's fire-log, and (only in
gc mode) embeds lesson identities via Ollama `nomic-embed-text` to surface
near-duplicates. No qmd-internal coupling, no API keys.

Usage:
  os_lessons.py health        compact summary (for /os)
  os_lessons.py gc            full report: cold / stale / duplicate candidates
  os_lessons.py gc --json     machine-readable report
Options:
  --cold-days N   (default 90)   never-fired + older than N days -> archive cand.
  --dup-min F     (default 0.82) cosine threshold for related candidates
  --merge-min F   (default 0.88) cosine threshold for true-duplicate candidates

Config (env, all optional):
  PERSONAL_OS_VAULT         vault location          (default ~/vault)
  PERSONAL_OS_HOME          dir with the fire-log   (default ~/.claude/personal-os)
  PERSONAL_OS_OLLAMA        ollama base URL         (default http://localhost:11434)
  PERSONAL_OS_EMBED_MODEL   embedding model         (default nomic-embed-text)
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import sys
import urllib.request

VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
LESSONS_DIR = os.path.join(VAULT, "lessons")
FIRE_LOG = os.path.join(
    os.path.expanduser(os.environ.get("PERSONAL_OS_HOME", "~/.claude/personal-os")),
    "lesson-fires.jsonl")
OLLAMA = os.environ.get("PERSONAL_OS_OLLAMA", "http://localhost:11434").rstrip("/") \
    + "/api/embeddings"
EMBED_MODEL = os.environ.get("PERSONAL_OS_EMBED_MODEL", "nomic-embed-text")


def today():
    return dt.date.today()


def parse_date(s):
    if not s:
        return None
    s = str(s).strip().strip('"').strip("'")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if not m:
        return None
    try:
        return dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def load_lessons():
    out = []
    for path in sorted(glob.glob(os.path.join(LESSONS_DIR, "*.md"))):
        try:
            text = open(path, encoding="utf-8").read()
        except Exception:
            continue
        fm, body = {}, text
        if text.startswith("---"):
            end = text.find("\n---", 3)
            if end != -1:
                block = text[3:end]
                body = text[end + 4:]
                for line in block.splitlines():
                    mm = re.match(r"^([A-Za-z_]+):\s*(.*)$", line)
                    if mm:
                        fm[mm.group(1).strip()] = mm.group(2).strip()
        rel = "lessons/" + os.path.basename(path)
        title = fm.get("title", "").strip('"').strip("'") or os.path.basename(path)[:-3]
        # representative identity text: title + the Rule line (or first real para)
        rule = ""
        for line in body.splitlines():
            s = line.strip()
            if s.startswith("**Regel") or s.startswith("**Rule"):
                rule = re.sub(r"\*\*|Regel\s*/\s*Rule:?", "", s).strip(" :*")
                break
        if not rule:
            for line in body.splitlines():
                s = line.strip()
                if s and not s.startswith("#") and not s.startswith("---") and len(s) > 20:
                    rule = s
                    break
        out.append({
            "path": rel, "file": path, "title": title,
            "created": parse_date(fm.get("created")),
            "updated": parse_date(fm.get("updated")) or parse_date(fm.get("created")),
            "review_by": parse_date(fm.get("review_by")),
            "confidence": fm.get("confidence", ""),
            "status": fm.get("status", ""),
            "rep": (title + " — " + rule)[:400],
        })
    return out


def load_fires():
    agg = {}
    if not os.path.exists(FIRE_LOG):
        return agg
    now = dt.datetime.now()
    for line in open(FIRE_LOG, encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("type", "hit") != "hit":  # miss records (zero/timeout/error) are not fires
            continue
        p = r.get("path")
        if not p:
            continue
        a = agg.setdefault(p, {"count": 0, "last": None, "d7": 0, "d30": 0})
        a["count"] += 1
        ts = r.get("ts", "")
        try:
            t = dt.datetime.fromisoformat(ts)
            if a["last"] is None or t > a["last"]:
                a["last"] = t
            age = (now - t).days
            if age <= 7:
                a["d7"] += 1
            if age <= 30:
                a["d30"] += 1
        except Exception:
            pass
    return agg


def embed(text):
    payload = json.dumps({"model": EMBED_MODEL, "prompt": text}).encode()
    req = urllib.request.Request(OLLAMA, data=payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp).get("embedding", [])


def cosine(a, b):
    import math
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def dup_pairs(lessons, threshold):
    try:
        import numpy as np
    except Exception:
        np = None
    vecs = []
    for ls in lessons:
        try:
            vecs.append(embed(ls["rep"]))
        except Exception:
            vecs.append(None)
    pairs = []
    n = len(lessons)
    if np is not None and all(v for v in vecs):
        M = np.array(vecs, dtype="float32")
        M = M / (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
        sim = M @ M.T
        for i in range(n):
            for j in range(i + 1, n):
                c = float(sim[i, j])
                if c >= threshold:
                    pairs.append((c, lessons[i]["path"], lessons[j]["path"]))
    else:
        for i in range(n):
            for j in range(i + 1, n):
                if vecs[i] and vecs[j]:
                    c = cosine(vecs[i], vecs[j])
                    if c >= threshold:
                        pairs.append((c, lessons[i]["path"], lessons[j]["path"]))
    pairs.sort(reverse=True)
    return pairs


def analyze(cold_days):
    lessons = load_lessons()
    fires = load_fires()
    t = today()
    for ls in lessons:
        f = fires.get(ls["path"], {})
        ls["fired"] = f.get("count", 0)
        ls["last_fired"] = f.get("last")
        ls["d30"] = f.get("d30", 0)
        ref = ls["updated"] or ls["created"]
        ls["age"] = (t - ref).days if ref else None
    cold = [l for l in lessons
            if l["fired"] == 0 and l["age"] is not None and l["age"] > cold_days]
    stale = [l for l in lessons if l["review_by"] and l["review_by"] < t]
    return lessons, cold, stale


def _wikilinks(relpath):
    try:
        t = open(os.path.join(VAULT, relpath), encoding="utf-8").read()
    except Exception:
        return set()
    return {w.split("|")[0].strip() for w in re.findall(r"\[\[([^\]]+)\]\]", t)}


def already_linked(a, b):
    """True if both lessons already reciprocally [[wikilink]] each other."""
    sa, sb = os.path.basename(a)[:-3], os.path.basename(b)[:-3]
    return sb in _wikilinks(a) and sa in _wikilinks(b)


def cmd_health(args):
    lessons, cold, stale = analyze(args.cold_days)
    total = len(lessons)
    fired_any = sum(1 for l in lessons if l["fired"] > 0)
    top = sorted(lessons, key=lambda l: -l["fired"])[:5]
    fires_total = sum(l["fired"] for l in lessons)
    d30 = sum(l["d30"] for l in lessons)
    print("LESSONS HEALTH ({}):".format(today()))
    print("  Total: {} lessons | ever fired: {} | never: {}".format(
        total, fired_any, total - fired_any))
    print("  Activations total: {} | last 30 days: {}".format(fires_total, d30))
    print("  Archive candidates (never fired, >{}d): {}".format(args.cold_days, len(cold)))
    print("  Stale (review_by overdue): {}".format(len(stale)))
    if any(l["fired"] for l in top):
        print("  Top firers:")
        for l in top:
            if l["fired"]:
                print("    {:>3}x  {}".format(l["fired"], l["path"]))
    print("  Deep duplicate check: /lessons-gc")


def cmd_gc(args):
    lessons, cold, stale = analyze(args.cold_days)
    pairs = dup_pairs(lessons, args.dup_min)
    merge = [p for p in pairs if p[0] >= args.merge_min]
    # Related band: pairs that already reciprocally link are handled -> don't re-flag
    # (otherwise GC cries wolf about the same handled case every run).
    related = [p for p in pairs if p[0] < args.merge_min and not already_linked(p[1], p[2])]
    if args.json:
        print(json.dumps({
            "total": len(lessons),
            "cold": [{"path": l["path"], "age": l["age"]} for l in cold],
            "stale": [{"path": l["path"], "review_by": str(l["review_by"])} for l in stale],
            "merge_pairs": [{"cosine": round(c, 3), "a": a, "b": b} for c, a, b in merge],
            "related_pairs": [{"cosine": round(c, 3), "a": a, "b": b} for c, a, b in related],
        }, ensure_ascii=False, indent=2))
        return
    print("=== LESSONS-GC REPORT ({}) ===".format(today()))
    print("Total: {} lessons\n".format(len(lessons)))
    print("— ARCHIVE CANDIDATES (never fired, >{}d old) [{}]:".format(args.cold_days, len(cold)))
    for l in sorted(cold, key=lambda x: -(x["age"] or 0)):
        print("   {:>4}d  {}".format(l["age"], l["path"]))
    print("\n— STALE (review_by overdue) [{}]:".format(len(stale)))
    for l in stale:
        print("   until {}  {}".format(l["review_by"], l["path"]))
    print("\n— MERGE CANDIDATES (cosine >= {}, true duplicate) [{}]:".format(args.merge_min, len(merge)))
    for c, a, b in merge:
        print("   {:.2f}  {}  <=>  {}".format(c, a, b))
    print("\n— RELATED / CROSS-LINK CHECK (cosine {:.2f}-{:.2f}) [{}]:".format(
        args.dup_min, args.merge_min, len(related)))
    for c, a, b in related:
        print("   {:.2f}  {}  <=>  {}".format(c, a, b))
    print("\nNext step: merge the MERGE band (preserve content); only reciprocally link the "
          "RELATED band (do NOT merge); move Cold to <vault>/_archive/lessons/; re-validate "
          "Stale. Never delete without a Y/N.")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    for name in ("health", "gc"):
        p = sub.add_parser(name)
        p.add_argument("--cold-days", type=int, default=90)
        p.add_argument("--dup-min", type=float, default=0.82)   # related floor
        p.add_argument("--merge-min", type=float, default=0.88)  # true-duplicate floor
        p.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.cmd == "health":
        cmd_health(args)
    elif args.cmd == "gc":
        cmd_gc(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
