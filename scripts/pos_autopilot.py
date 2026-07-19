#!/usr/bin/env python3
"""pos_autopilot.py — tier-0/1 executor: the OS acts silently instead of asking ($0, local).

Background: the nightly passes (dream.py) compute good decisions and then ASKED —
and the proposal notes piled up unreviewed. From now on the low-risk layer is
EXECUTED: every action goes through pos_actions.journal() with verbatim undo data,
and /undo rolls a whole night back in under a minute. Feedback happens implicitly
(pos_actions.py collect-feedback).

Subcommands (all fail-open, each cap-limited, kill switch <PERSONAL_OS_HOME>/autopilot.off):
  act-links    reciprocal [[wikilinks]] from the connections pass (>= pass threshold, cap 6)
  act-dreams   dream notes >3d: status draft -> superseded (frontmatter field only)
  act-refs     machine-generated refs cards >21d outside the top 30 -> _inbox/refs/_archive/
               (--dry-run for a safe preview / one-time drain of an old backlog)
  act-mine     chat-mining drain: cap 10/night, LLM triage (no substance -> state advance;
               substance -> lesson draft to _inbox/lessons/, qmd dedupe >= 80)
  act-harvest  harvest-queue drain: cap 5/night (already saved -> done; else draft)
  notify       ONE morning notification (own debounce channel, no alarm sound)

NEVER autonomous: deleting anything · curated note bodies (except the ## Links append) ·
writing into autopush-allowlisted dirs beyond the above · chats/ raw files · profile/ content.

Config (env, all optional): PERSONAL_OS_HOME, PERSONAL_OS_VAULT, PERSONAL_OS_OLLAMA,
PERSONAL_OS_DREAM_MODEL, PERSONAL_OS_EMBED_MODEL (see dream.py).
"""
from __future__ import annotations
import argparse
import datetime as dt
import glob
import hashlib
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dream
import pos_actions
import pos_utils
import qmd_search

PO = pos_utils.PO
VAULT = dream.VAULT
KILL = os.path.join(PO, "autopilot.off")
CURATED = ("lessons/", "knowledge/", "ideas/", "projects/", "permanent/", "profile/")
LINK_CAP = 6
ARCHIVE_DAYS = 21
KEEP_TOP = 30
MTIME_GUARD_MIN = 30
DRAFTS_DIR = os.path.join(VAULT, "_inbox", "lessons")
REFS_DIR = os.path.join(VAULT, "_inbox", "refs")
REFS_ARCHIVE = os.path.join(REFS_DIR, "_archive")
# both chat import streams (see /mine-chats): (subdir under <vault>/chats, state file)
CHAT_SOURCES = (("code", ".chat_mining_state.txt"), ("gpt", ".chatgpt_mining_state.txt"))
HQ = os.path.join(PO, "harvest-queue.jsonl")
HQ_DONE = os.path.join(PO, "harvest-queue-done.jsonl")


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def killed() -> bool:
    if os.path.exists(KILL):
        log("[autopilot] autopilot.off present — skipping")
        return True
    return False


def today(args) -> str:
    return getattr(args, "date", None) or dt.date.today().isoformat()


def _load_pass(args, name: str) -> dict:
    try:
        return json.load(open(os.path.join(dream.WORK_ROOT, today(args), name + ".json")))
    except Exception:
        return {}


def _slug(text: str) -> str:
    s = re.sub(r"[^a-z0-9äöüß]+", "-", text.lower()).strip("-")[:60]
    return s or "note"


def _is_no(verdict: str) -> bool:
    return bool(re.match(r"\s*no\b", verdict, re.I))


# ------------------------------------------------------------- act-links (tier 0a)
def _append_link(path: str, line: str) -> None:
    text = open(path, encoding="utf-8").read()
    lines = text.splitlines()
    if "## Links" in lines:
        idx = lines.index("## Links")
        j = idx + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        while j > idx + 1 and lines[j - 1].strip() == "":
            j -= 1
        lines.insert(j, line)
        new = "\n".join(lines) + ("\n" if text.endswith("\n") else "")
    else:
        new = text.rstrip("\n") + "\n\n## Links\n" + line + "\n"
    pos_utils.write_atomic(path, new)


def cmd_act_links(args) -> None:
    if killed():
        return
    d = today(args)
    p = dream.adaptive_params("connections")
    sugg = [s for s in (_load_pass(args, "connections").get("suggestions") or [])
            if s.get("score", 0) >= p.get("threshold", 100)]
    sugg.sort(key=lambda s: -s["score"])
    done = 0
    for s in sugg:
        if done >= LINK_CAP:
            break
        ra, rb = s["a"], s["b"]
        if not (ra.startswith(CURATED) and rb.startswith(CURATED)):
            continue
        fa, fb = os.path.join(VAULT, ra), os.path.join(VAULT, rb)
        if not (os.path.exists(fa) and os.path.exists(fb)):
            continue
        try:  # concurrent-edit guard: never touch files being worked on right now
            if min(time.time() - os.path.getmtime(fa),
                   time.time() - os.path.getmtime(fb)) < MTIME_GUARD_MIN * 60:
                continue
        except OSError:
            continue
        sa = os.path.basename(fa)[:-3]
        sb = os.path.basename(fb)[:-3]
        if sb.lower() in dream.wikilinks_of(fa) or sa.lower() in dream.wikilinks_of(fb):
            continue
        la = f"- [[{sb}]] — auto-link {d} (connections {s['score']})"
        lb = f"- [[{sa}]] — auto-link {d} (connections {s['score']})"
        # record whether the append CREATES the section, so /undo can strip the
        # then-empty heading again (verbatim roundtrip)
        new_sec_a = "## Links" not in open(fa, encoding="utf-8").read().splitlines()
        new_sec_b = "## Links" not in open(fb, encoding="utf-8").read().splitlines()
        _append_link(fa, la)
        _append_link(fb, lb)
        pos_actions.journal({
            "action": "link.add", "night": d, "targets": [fa, fb],
            "evidence": {"pass": "connections", "score": s["score"],
                         "snippet": s.get("snippet", "")[:120]},
            "undo": {"op": "remove_lines",
                     "items": [{"path": fa, "line": la, "added_section": new_sec_a},
                               {"path": fb, "line": lb, "added_section": new_sec_b}]},
        })
        done += 1
    log(f"[act-links] {done} links added ({len(sugg)} candidates)")


# ------------------------------------------------------------ act-dreams (tier 0c)
def cmd_act_dreams(args) -> None:
    if killed():
        return
    d = today(args)
    cutoff = dt.date.fromisoformat(d) - dt.timedelta(days=3)
    n = 0
    for f in sorted(glob.glob(os.path.join(VAULT, "_inbox", "dreams", "*.md"))):
        m = re.match(r"(\d{4}-\d{2}-\d{2})", os.path.basename(f))
        if not m or dt.date.fromisoformat(m.group(1)) >= cutoff:
            continue
        text = open(f, encoding="utf-8", errors="replace").read()
        if "status: draft" not in text[:400]:
            continue
        pos_utils.write_atomic(f, text.replace("status: draft", "status: superseded", 1))
        pos_actions.journal({
            "action": "note.status", "night": d, "targets": [f],
            "undo": {"op": "set_status", "path": f, "old": "draft", "new": "superseded"},
        })
        n += 1
    log(f"[act-dreams] {n} old dream notes superseded")


# -------------------------------------------------------------- act-refs (tier 0b)
def _refs_cards() -> list[str]:
    """Live cards in _inbox/refs (without _INDEX/_DIGEST; _archive/ is a subfolder
    and falls out of the *.md glob automatically)."""
    return sorted(f for f in glob.glob(os.path.join(REFS_DIR, "*.md"))
                  if not os.path.basename(f).startswith(("_INDEX", "_DIGEST")))


def _active_hub_vecs() -> list[dict]:
    """[{name, vec}] for active project hubs (nomic-embed via ollama)."""
    hubs = []
    for f in glob.glob(os.path.join(VAULT, "projects", "*.md")):
        try:
            t = open(f, encoding="utf-8", errors="replace").read(3000)
        except Exception:
            continue
        if re.search(r"^status:\s*active", t, re.M):
            title, body = dream.read_note(f, 800)
            try:
                hubs.append({"name": os.path.basename(f)[:-3],
                             "vec": dream.ollama_embed(title + " " + body)})
            except Exception:
                pass
    return hubs


def _score_refs_cards(cards: list[str], hubs: list[dict], max_new_embeds: int = 200):
    """Scores every card against its best hub; uses/extends dream.py's embed cache.
    Returns (scored:[{card,path,hub,score}] sorted desc, new_embeds, deferred)."""
    cache = {}
    try:
        cache = json.load(open(dream.EMBED_CACHE))
    except Exception:
        pass
    new_embeds = deferred = 0
    scored = []
    for f in cards:
        try:
            mt = os.path.getmtime(f)
        except OSError:
            continue
        ent = cache.get(f)
        if not ent or ent.get("mtime") != mt:
            if new_embeds >= max_new_embeds:
                deferred += 1  # no silent cap — this shows up in the log
                continue
            title, body = dream.read_note(f, 1200)
            try:
                cache[f] = {"mtime": mt, "vec": dream.ollama_embed(title + " " + body)}
                new_embeds += 1
            except Exception:
                continue
        vec = cache[f]["vec"]
        best = max(((dream.cosine(vec, h["vec"]), h["name"]) for h in hubs), default=(0, "?"))
        scored.append({"card": os.path.relpath(f, VAULT), "path": f,
                       "hub": best[1], "score": round(best[0], 3)})
    pos_utils.write_atomic(dream.EMBED_CACHE, cache)
    scored.sort(key=lambda s: -s["score"])
    return scored, new_embeds, deferred


def cmd_act_refs(args) -> None:
    if killed():
        return
    if not dream.ollama_up():
        return log("[act-refs] ollama not reachable — skipping (scores needed)")
    d = today(args)
    hubs = _active_hub_vecs()
    if not hubs:
        return log("[act-refs] no active hubs — skipping")
    cards = _refs_cards()
    scored, _, deferred = _score_refs_cards(cards, hubs)
    now = time.time()
    planned = []
    for s in scored[KEEP_TOP:]:
        f = s["path"]
        try:
            if (now - os.path.getmtime(f)) / 86400 <= ARCHIVE_DAYS:
                continue
        except OSError:
            continue
        head = open(f, encoding="utf-8", errors="replace").read(400)
        if not re.search(r"^status:\s*(inbox|parked)", head, re.M):
            continue  # unknown provenance -> never touch autonomously
        planned.append(s)
    if args.dry_run:
        log(f"[act-refs] DRY-RUN: {len(planned)} of {len(cards)} cards would be archived "
            f"(top {KEEP_TOP} + <{ARCHIVE_DAYS}d stay; {deferred} without an embedding)")
        for s in planned[:10]:
            log(f"   {s['card']} (score {s['score']})")
        return
    os.makedirs(REFS_ARCHIVE, exist_ok=True)
    n = 0
    for s in planned:
        f = s["path"]
        dest = os.path.join(REFS_ARCHIVE, os.path.basename(f))
        if os.path.exists(dest):
            continue
        try:
            os.rename(f, dest)
        except OSError:
            continue
        pos_actions.journal({
            "action": "card.archive", "night": d, "targets": [f],
            "evidence": {"pass": "triage", "score": s["score"], "hub": s["hub"]},
            "undo": {"op": "move", "from": f, "to": dest},
        })
        n += 1
    log(f"[act-refs] {n} cards archived · {len(cards) - n} live")


# -------------------------------------------------------------- act-mine (tier 0d/1)
def _mined(state_path: str) -> set[str]:
    try:
        return {l.strip() for l in open(state_path, encoding="utf-8") if l.strip()}
    except FileNotFoundError:
        return set()


def _advance_state(state_path: str, name: str, d: str, reason: str,
                   pname: str = "mining") -> None:
    with open(state_path, "a", encoding="utf-8") as f:
        f.write(name + "\n")
    pos_actions.journal({
        "action": "state.advance", "night": d, "targets": [name],
        "evidence": {"pass": pname, "reason": reason[:200]},
        "undo": {"op": "remove_state_line", "path": state_path, "line": name},
    })


def _write_draft(d: str, title: str, body: str, source: str, pname: str) -> str | None:
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = os.path.join(DRAFTS_DIR, f"auto-{_slug(title)}.md")
    if os.path.exists(path):
        return None
    note = (f"---\ntitle: \"auto: {title[:120]}\"\ntags: [lesson, auto-draft]\n"
            f"created: {d}\nupdated: {d}\nstatus: draft\ntype: lesson\nconfidence: low\n"
            f"source: {source}\n---\n\n"
            f"> Auto-draft ({pname}, {dream.GEN_MODEL}) — review, sharpen, then promote "
            f"to your lessons/ folder, or just leave it (45d untouched = a signal).\n\n"
            + body.strip() + "\n")
    pos_utils.write_atomic(path, note)
    pos_actions.journal({
        "action": "draft.create", "night": d, "targets": [path],
        "evidence": {"pass": pname, "hash": hashlib.sha256(note.encode()).hexdigest()[:16],
                     "source": source},
        "undo": {"op": "move", "from": os.path.join(VAULT, "_inbox", "_undone",
                                                    os.path.basename(path)), "to": path},
    })
    return path


def _dedupe_hit(title: str) -> str | None:
    res = qmd_search.vsearch(title, n=3, timeout=20)
    for h in res.get("hits", []):
        if h["path"].startswith("lessons/") and h["score"] >= 80:
            return h["path"]
    return None


def cmd_act_mine(args) -> None:
    if killed():
        return
    if not dream.ollama_up():
        return log("[act-mine] ollama not reachable — skipping")
    d = today(args)
    todo = []
    for sub, state_file in CHAT_SOURCES:
        state_path = os.path.join(VAULT, state_file)
        mined = _mined(state_path)
        todo += [(f, state_path)
                 for f in glob.glob(os.path.join(VAULT, "chats", sub, "*.md"))
                 if os.path.basename(f) not in mined]
    todo = sorted(todo, key=lambda t: os.path.getmtime(t[0]))[:args.cap]
    drafted = advanced = 0
    for f, state_path in todo:
        name = os.path.basename(f)
        title, body = dream.read_note(f, 5000)
        try:
            verdict = dream.ollama_generate(
                "Check this excerpt from a coding-session chat: does it contain a "
                "TRANSFERABLE lesson (a mistake + its fix + why, useful across projects)? "
                "Answer in EXACTLY one line: 'YES: <lesson title as a rule sentence>' or "
                "'NO: <short reason>'. No other output.\n\nTITLE: "
                + title + "\n\n" + body[:4500], timeout=90)
        except Exception as e:
            log(f"[act-mine] WARN LLM: {e}")
            break
        if _is_no(verdict):
            _advance_state(state_path, name, d, verdict[:200])
            advanced += 1
            continue
        lesson_title = verdict.split(":", 1)[-1].strip() if ":" in verdict else title
        dupe = _dedupe_hit(lesson_title)
        if dupe:
            _advance_state(state_path, name, d, f"duplicate-of: {dupe}")
            advanced += 1
            continue
        try:
            draft = dream.ollama_generate(
                "Distill ONE transferable lesson from this chat as markdown with the "
                "sections '## Mistake', '## Fix' and '## Why' (1-3 concrete bullets "
                "each). Do not invent anything.\n\nLESSON TITLE: " + lesson_title
                + "\n\nCHAT:\n" + body[:4500], timeout=120)
        except Exception as e:
            log(f"[act-mine] WARN draft LLM: {e}")
            break
        if draft and _write_draft(d, lesson_title, draft, os.path.relpath(f, VAULT), "mining"):
            drafted += 1
        _advance_state(state_path, name, d, f"drafted: {lesson_title[:80]}")
    log(f"[act-mine] {advanced + drafted}/{len(todo)} chats processed · {drafted} drafts")


# ----------------------------------------------------------- act-harvest (tier 0e/1)
def _saved_re() -> re.Pattern:
    """A session that already wrote a vault log was harvested by /save — regex keyed on
    the vault BASENAME (mirrors save_nudge.sh), covering fallback and project logs/."""
    vb = os.path.basename(VAULT.rstrip("/")) or "vault"
    return re.compile(r'"file_path":"[^"]*' + re.escape(vb) + r'/([^"]*/)?logs/[^"]*\.md"')


# Meta-phrases = the small judge model summarizing the chat instead of finding a
# lesson → treat as NO. EN + DE (bilingual vaults).
GARBAGE_TITLE = re.compile(
    r"^(it (seems|appears|looks)|the (conversation|chat|assistant|session|user)"
    r"|this (conversation|chat|session)|in (this|the) (chat|session|conversation)"
    r"|summary|here('s| is)|unfortunately|based on"
    r"|es scheint|die konversation|der (chat|assistent)|zusammenfassung|hier ist|leider)",
    re.I)


def _transcript_text(raw: str, max_chars: int = 9000) -> str:
    """Pull readable text out of a JSONL transcript (instead of dumping raw JSON into
    the small model's prompt — that produced summary mush instead of lessons)."""
    chunks = []
    for line in raw.splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        msg = r.get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content)
        elif isinstance(content, list):
            for c in content:
                if isinstance(c, dict) and c.get("type") == "text" and c.get("text"):
                    chunks.append(c["text"])
    return "\n".join(chunks)[-max_chars:]


def cmd_act_harvest(args) -> None:
    if killed():
        return
    d = today(args)
    try:
        entries = [json.loads(l) for l in open(HQ, encoding="utf-8", errors="replace")
                   if l.strip()]
    except FileNotFoundError:
        return log("[act-harvest] queue empty")
    if not entries:
        return log("[act-harvest] queue empty")
    llm = dream.ollama_up()
    saved_re = _saved_re()
    batch = entries[:args.cap]
    processed, drafted = [], 0
    for e in batch:
        tp = e.get("transcript_path") or ""
        reason = None
        if not os.path.exists(tp):
            reason = "transcript-gone"
        else:
            try:
                text = open(tp, encoding="utf-8", errors="replace").read()
            except Exception:
                text = ""
            if saved_re.search(text):
                reason = "already-saved"
            elif not llm:
                break  # LLM needed, ollama down → abort the batch, queue stays
            else:
                convo = _transcript_text(text)
                if len(convo) < 500:
                    reason = "no-lesson: too little readable content"
                else:
                    try:
                        verdict = dream.ollama_generate(
                            "Below is the end of a coding session. Does it contain a "
                            "TRANSFERABLE lesson: a concrete mistake that got fixed, WITH "
                            "a rule that protects future sessions from it? WHEN IN DOUBT "
                            "SAY NO — plain feature work, status reports, or abandoned "
                            "chats are NOT a lesson. Answer EXACTLY: 'YES: <rule as an "
                            "imperative sentence>' or 'NO: <reason>'.\n\n" + convo,
                            timeout=90)
                    except Exception as ex:
                        log(f"[act-harvest] WARN LLM: {ex}")
                        break
                if reason is None:
                    if (_is_no(verdict)
                            or GARBAGE_TITLE.search(verdict.split(":", 1)[-1].strip())):
                        reason = "no-lesson: " + verdict[:120]
                    else:
                        lt = verdict.split(":", 1)[-1].strip() or "session-lesson"
                        dupe = _dedupe_hit(lt)
                        if dupe:
                            reason = f"duplicate-of: {dupe}"
                        else:
                            try:
                                draft = dream.ollama_generate(
                                    "Distill THE one lesson of this session as markdown "
                                    "('## Mistake', '## Fix', '## Why', 1-3 concrete "
                                    "bullets each). Do not invent anything and do NOT "
                                    "summarize the chat — only the lesson.\n\nTITLE: "
                                    + lt + "\n\n" + convo, timeout=120)
                            except Exception as ex:
                                log(f"[act-harvest] WARN draft: {ex}")
                                break
                            if draft and _write_draft(d, lt, draft, tp, "harvest"):
                                drafted += 1
                            reason = "drafted"
        if reason is None:
            break
        processed.append(e)
        with open(HQ_DONE, "a", encoding="utf-8") as f:
            f.write(json.dumps({**e, "done_ts": pos_actions._now(), "reason": reason},
                               ensure_ascii=False) + "\n")
        pos_actions.journal({
            "action": "queue.done", "night": d, "targets": [e.get("session_id", "?")],
            "evidence": {"pass": "harvest", "reason": reason},
            "undo": {"op": "requeue", "queue": HQ, "done": HQ_DONE,
                     "line": json.dumps(e, ensure_ascii=False)},
        })
    if processed:
        done_ids = {e.get("session_id") for e in processed}
        keep = [json.dumps(e, ensure_ascii=False) for e in entries
                if e.get("session_id") not in done_ids]
        pos_utils.write_atomic(HQ, "\n".join(keep) + ("\n" if keep else ""))
    log(f"[act-harvest] {len(processed)} sessions processed · {drafted} drafts · "
        f"{len(entries) - len(processed)} remain")


# ------------------------------------------------------------------ notify
def pick_headline(args) -> str:
    fires = _load_pass(args, "fires")
    hot = fires.get("hot_lessons") or []
    if hot:
        h = hot[0]
        stem = os.path.splitext(os.path.basename(h["path"]))[0]
        return f"{stem} fired {h['count']}x — sharpen the rule?"
    gc = _load_pass(args, "gc")
    if gc.get("merge_pairs"):
        pr = gc["merge_pairs"][0]
        return ("merge candidate: "
                + os.path.splitext(os.path.basename(pr["a"]))[0][:40] + " + "
                + os.path.splitext(os.path.basename(pr["b"]))[0][:40])
    tri = _load_pass(args, "triage")
    if tri.get("top") and tri["top"][0].get("score", 0) > 0.75:
        t = tri["top"][0]
        return f"top card: {os.path.basename(t['card'])[:50]} -> {t['hub']}"
    res = _load_pass(args, "residue")
    for line in (res.get("synthesis") or "").splitlines():
        if "Suggestion for today" in line:
            return line.strip("-• ").strip()[:120]
    return ""


def cmd_notify(args) -> None:
    d = today(args)
    acts = [a for a in pos_actions._read_journal()
            if a.get("night") == d and a.get("action") not in ("undo", "undo.skipped")]
    counts = {}
    for a in acts:
        counts[a["action"]] = counts.get(a["action"], 0) + 1
    if not acts:
        return log("[notify] no actions — staying quiet")
    parts = []
    if counts.get("link.add"):
        parts.append(f"{counts['link.add']} links")
    if counts.get("card.archive"):
        parts.append(f"{counts['card.archive']} archived")
    if counts.get("draft.create"):
        parts.append(f"{counts['draft.create']} drafts")
    if counts.get("state.advance") or counts.get("queue.done"):
        parts.append(f"{counts.get('state.advance', 0) + counts.get('queue.done', 0)} queue items")
    head = pick_headline(args)
    msg = "OS overnight: " + ", ".join(parts) + (f" · hint: {head}" if head else "") \
          + " · /undo available"
    # own debounce channel (separate from the degraded alarm), no alarm sound
    hj = {}
    try:
        hj = json.load(open(os.path.join(PO, "health.json")))
    except Exception:
        pass
    if (hj.get("notified_autopilot") or {}).get("date") == d:
        return log("[notify] already notified today")
    try:
        import pos_health
        pos_health._notify("Personal OS autopilot", msg)
    except Exception:
        pass
    hj["notified_autopilot"] = {"date": d}
    pos_utils.write_atomic(os.path.join(PO, "health.json"), hj)
    log(f"[notify] {msg}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["act-links", "act-dreams", "act-refs", "act-mine",
                                    "act-harvest", "notify"])
    ap.add_argument("--date")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--cap", type=int, default=None)
    args = ap.parse_args()
    if args.cap is None:
        args.cap = {"act-mine": 10, "act-harvest": 5}.get(args.cmd, 0)
    {"act-links": cmd_act_links, "act-dreams": cmd_act_dreams, "act-refs": cmd_act_refs,
     "act-mine": cmd_act_mine, "act-harvest": cmd_act_harvest, "notify": cmd_notify}[args.cmd](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
