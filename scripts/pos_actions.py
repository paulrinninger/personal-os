#!/usr/bin/env python3
"""pos_actions.py — action journal + undo for the Personal OS autopilot ($0, stdlib).

The trust foundation of the "act silently instead of asking" inversion: the autopilot
may execute tier-0 actions overnight (append links, archive machine-generated cards,
set status fields, write state lines) BECAUSE every action is journaled here with
verbatim undo data, and /undo rolls a whole night back in under a minute.
Safety = post-hoc undo instead of up-front approval (which never happened —
the proposal notes piled up unreviewed).

Journal: <PERSONAL_OS_HOME>/actions.jsonl (outside the vault — never committed).
Record: {"id","ts","night","action","targets":[...],"evidence":{...},"undo":{...}}
Undo ops (each with a precondition check — if the user already changed it → skip+journal):
  remove_lines      {"items":[{"path","line","added_section"?}]}
                                                  remove the exact line from file(s);
                                                  added_section also strips a now-empty
                                                  trailing "## Links" heading the action
                                                  itself created (verbatim roundtrip)
  move              {"from","to"}                 move the file back
  set_status        {"path","old","new"}          revert a frontmatter status field
  remove_state_line {"path","line"}               remove a line from a state file
  requeue           {"queue","done","line"}       put a queue entry back, drop the done row

Every executed undo automatically writes a `rejected` row into dream-feedback.jsonl
(pass taken from evidence.pass) — an undo IS the strongest feedback signal.

Subcommands:
  list [--night YYYY-MM-DD|--last N|--action X]
  undo [--last N|--night YYYY-MM-DD|--id aXXXXXXXX-NNN] [--dry-run]
  journal '<json>'
  collect-feedback          implicit feedback scanner (48h–30d grace) → dream-feedback.jsonl

Config (env, all optional):
  PERSONAL_OS_HOME   state home (journal, feedback, scan sidecar)  (default ~/.claude/personal-os)
  PERSONAL_OS_VAULT  vault location                                (default ~/vault)
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pos_utils

PO = pos_utils.PO
JOURNAL = os.path.join(PO, "actions.jsonl")
FEEDBACK = os.path.join(PO, "dream-feedback.jsonl")
SCAN_STATE = os.path.join(PO, "feedback-scan.json")
VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))
UNDONE_DIR = os.path.join(VAULT, "_inbox", "_undone")


def _now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def _read_journal() -> list[dict]:
    out = []
    try:
        for line in open(JOURNAL, encoding="utf-8", errors="replace"):
            try:
                out.append(json.loads(line))
            except Exception:
                pass
    except FileNotFoundError:
        pass
    return out


def journal(rec: dict) -> str:
    """Append-only under a lock; assigns the id (a<night>-<seq>)."""
    with_lock = pos_utils.acquire_lock("actions", stale_hours=1.0, wait_secs=10)
    try:
        night = rec.get("night") or dt.date.today().isoformat()
        seq = sum(1 for r in _read_journal() if r.get("night") == night) + 1
        rec = dict(rec)
        rec.setdefault("ts", _now())
        rec["night"] = night
        rec["id"] = f"a{night.replace('-', '')}-{seq:03d}"
        os.makedirs(PO, exist_ok=True)
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return rec["id"]
    finally:
        if with_lock:
            pos_utils.release_lock("actions")


def _feedback(action: dict, verdict: str) -> None:
    ev = action.get("evidence") or {}
    if not ev.get("pass"):
        return
    try:
        with open(FEEDBACK, "a", encoding="utf-8") as f:
            f.write(json.dumps({"id": ev.get("block_id") or action.get("id"),
                                "pass": ev["pass"], "verdict": verdict,
                                "ts": _now(), "source": "pos_actions"},
                               ensure_ascii=False) + "\n")
    except Exception:
        pass


# ------------------------------------------------------------------ undo ops
def _remove_line_from(path: str, line: str) -> bool:
    """True = the exact line was present and has been removed (atomically)."""
    try:
        text = open(path, encoding="utf-8").read()
    except Exception:
        return False
    needle = line.rstrip("\n")
    lines = text.splitlines()
    if needle not in lines:
        return False
    lines.remove(needle)  # first exact instance
    pos_utils.write_atomic(path, "\n".join(lines) + ("\n" if text.endswith("\n") else ""))
    return True


def _strip_empty_links_section(path: str) -> None:
    """After removing an auto-link whose action CREATED the '## Links' section, the
    empty heading would dangle at EOF — strip it so the undo is verbatim. Only fires
    when nothing but whitespace follows the heading (user-added links keep it)."""
    try:
        text = open(path, encoding="utf-8").read()
    except Exception:
        return
    new = re.sub(r"\n*## Links\s*\Z", "\n", text)
    if new != text:
        pos_utils.write_atomic(path, new)


def _set_status(path: str, old: str, new: str) -> bool:
    """Reverts frontmatter status new→old; only if it currently reads new."""
    try:
        text = open(path, encoding="utf-8").read()
    except Exception:
        return False
    cur = f"status: {new}"
    want = f"status: {old}"
    if cur not in text.split("\n---", 2)[0] + "\n":
        # the status line must sit in the frontmatter block
        head = text[:400]
        if cur not in head:
            return False
    idx = text.find(cur)
    if idx < 0:
        return False
    pos_utils.write_atomic(path, text[:idx] + want + text[idx + len(cur):])
    return True


def _undo_one(action: dict, dry: bool = False) -> str:
    """Returns: 'undone' | 'skipped:<reason>'. Precondition checks ALWAYS run first."""
    u = action.get("undo") or {}
    op = u.get("op")
    if action.get("action") in ("undo", "undo.skipped"):
        return "skipped:meta"
    if op == "remove_lines":
        items = u.get("items") or []
        present = [it for it in items
                   if os.path.exists(it["path"])
                   and it["line"].rstrip("\n") in open(it["path"], encoding="utf-8",
                                                      errors="replace").read().splitlines()]
        if not present:
            return "skipped:lines-already-gone"
        if dry:
            return "undone"
        for it in present:
            _remove_line_from(it["path"], it["line"])
            if it.get("added_section"):
                _strip_empty_links_section(it["path"])
        return "undone"
    if op == "move":
        src, dst = u.get("to"), u.get("from")  # undo: to → from
        if not (src and dst) or not os.path.exists(src):
            return "skipped:file-not-at-destination"
        if os.path.exists(dst):
            return "skipped:original-path-occupied"
        if dry:
            return "undone"
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        os.rename(src, dst)
        return "undone"
    if op == "set_status":
        if not os.path.exists(u.get("path", "")):
            return "skipped:file-gone"
        if dry:
            return "undone"
        ok = _set_status(u["path"], u["old"], u["new"])
        return "undone" if ok else "skipped:status-already-changed"
    if op == "remove_state_line":
        if not os.path.exists(u.get("path", "")):
            return "skipped:state-file-gone"
        if dry:
            return "undone"
        ok = _remove_line_from(u["path"], u["line"])
        return "undone" if ok else "skipped:line-already-gone"
    if op == "requeue":
        # Undo of queue.done: put the entry back into the live queue, drop the done row
        line = (u.get("line") or "").rstrip("\n")
        if not line:
            return "skipped:no-entry"
        try:
            live = open(u["queue"], encoding="utf-8", errors="replace").read() \
                if os.path.exists(u["queue"]) else ""
        except Exception:
            return "skipped:queue-unreadable"
        if line in live.splitlines():
            return "skipped:already-in-queue"
        if dry:
            return "undone"
        with open(u["queue"], "a", encoding="utf-8") as f:
            f.write(line + "\n")
        if os.path.exists(u.get("done", "")):
            # The done row starts from the same entry JSON (plus done_ts/reason) —
            # match by session_id and remove it
            try:
                sid = json.loads(line).get("session_id")
                rows = [l for l in open(u["done"], encoding="utf-8", errors="replace")
                        if l.strip() and json.loads(l).get("session_id") != sid]
                pos_utils.write_atomic(u["done"], "".join(rows))
            except Exception:
                pass
        return "undone"
    return f"skipped:unknown-op:{op}"


def cmd_undo(args) -> int:
    acts = [a for a in _read_journal() if a.get("action") not in ("undo", "undo.skipped")]
    undone_ids = {a.get("of") for a in _read_journal() if a.get("action") == "undo"}
    acts = [a for a in acts if a["id"] not in undone_ids]
    if args.id:
        sel = [a for a in acts if a["id"] == args.id]
    elif args.night:
        sel = [a for a in acts if a.get("night") == args.night]
    else:
        sel = acts[-(args.last or 1):]
    if not sel:
        print("nothing to undo (already rolled back, or no matches)")
        return 0
    n_done = n_skip = 0
    for a in reversed(sel):  # backwards: most recent action reverts first
        res = _undo_one(a, dry=args.dry_run)
        label = f"{a['id']} {a['action']} {os.path.basename(str((a.get('targets') or ['?'])[0]))}"
        if res == "undone":
            n_done += 1
            print(f"  ↩ {label}")
            if not args.dry_run:
                journal({"action": "undo", "of": a["id"], "night": dt.date.today().isoformat()})
                _feedback(a, "rejected")
        else:
            n_skip += 1
            print(f"  ~ {label} — {res}")
            if not args.dry_run:
                journal({"action": "undo.skipped", "of": a["id"], "reason": res,
                         "night": dt.date.today().isoformat()})
    print(f"{'DRY-RUN: ' if args.dry_run else ''}{n_done} undone · {n_skip} skipped")
    return 0


def cmd_list(args) -> int:
    acts = _read_journal()
    if args.night:
        acts = [a for a in acts if a.get("night") == args.night]
    if args.action:
        acts = [a for a in acts if a.get("action") == args.action]
    if args.last:
        acts = acts[-args.last:]
    by = {}
    for a in acts:
        by.setdefault(a.get("action", "?"), []).append(a)
    for act, rows in sorted(by.items()):
        print(f"{act} ({len(rows)}):")
        for a in rows[-20:]:
            tgt = ", ".join(os.path.basename(str(t)) for t in (a.get("targets") or [])[:2])
            ev = a.get("evidence") or {}
            extra = f" [{ev.get('pass', '')}{' ' + str(ev.get('score')) if ev.get('score') else ''}]" \
                if ev.get("pass") else ""
            print(f"  {a['id']}  {tgt}{extra}")
    if not acts:
        print("journal empty (for this filter)")
    return 0


# ------------------------------------------------- implicit feedback scanner
def _file_hash(path: str) -> str:
    try:
        return hashlib.sha256(open(path, "rb").read()).hexdigest()[:16]
    except Exception:
        return ""


def cmd_collect_feedback(_args) -> int:
    """Implicit feedback without a ritual: what the user DID with the auto-artifacts
    becomes the accepted/rejected signal for adaptive_params. 48h grace (a chance to
    notice), verdict at the latest after the type-specific deadlines. The sidecar
    prevents double-scoring."""
    state = {}
    try:
        state = json.load(open(SCAN_STATE))
    except Exception:
        pass
    now = dt.datetime.now()
    scored = 0
    for a in _read_journal():
        aid = a.get("id")
        if not aid or aid in state or a.get("action") in ("undo", "undo.skipped"):
            continue
        try:
            age_h = (now - dt.datetime.fromisoformat(a["ts"])).total_seconds() / 3600
        except Exception:
            continue
        if age_h < 48 or age_h > 30 * 24:
            if age_h > 30 * 24:
                state[aid] = "expired"
            continue
        verdict = None
        act, u = a.get("action"), a.get("undo") or {}
        if act == "link.add":
            items = u.get("items") or []
            gone = any(os.path.exists(it["path"]) and it["line"].rstrip("\n") not in
                       open(it["path"], encoding="utf-8", errors="replace").read().splitlines()
                       for it in items)
            if gone:
                verdict = "rejected"       # the user removed the link
            elif age_h >= 14 * 24:
                verdict = "accepted"       # survived two weeks
        elif act == "card.archive":
            dst = u.get("to", "")
            back = os.path.join(os.path.dirname(os.path.dirname(dst)), os.path.basename(dst))
            if os.path.exists(back):
                verdict = "rejected"       # pulled back out of the archive
            elif age_h >= 14 * 24 and os.path.exists(dst):
                verdict = "accepted"
        elif act == "draft.create":
            draft = (a.get("targets") or [""])[0]
            slug = os.path.basename(draft)
            promoted = os.path.join(VAULT, "lessons", slug.replace("auto-", "", 1))
            if os.path.exists(os.path.join(UNDONE_DIR, slug)):
                verdict = "rejected"
            elif os.path.exists(promoted):
                verdict = "accepted"       # promoted
            elif os.path.exists(draft) and (a.get("evidence") or {}).get("hash") \
                    and _file_hash(draft) != a["evidence"]["hash"]:
                verdict = "accepted"       # edited
            elif age_h >= 45 * 24:
                verdict = "rejected"       # untouched for 45d
        # note.status / state.advance / queue.done: no signal value
        if verdict:
            _feedback(a, verdict)
            state[aid] = verdict
            scored += 1
    pos_utils.write_atomic(SCAN_STATE, state)
    print(f"collect-feedback: {scored} verdicts written")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd")
    p = sub.add_parser("list")
    p.add_argument("--night"); p.add_argument("--last", type=int); p.add_argument("--action")
    p = sub.add_parser("undo")
    p.add_argument("--last", type=int); p.add_argument("--night"); p.add_argument("--id")
    p.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("journal")
    p.add_argument("json")
    sub.add_parser("collect-feedback")
    args = ap.parse_args()
    if args.cmd == "list":
        return cmd_list(args)
    if args.cmd == "undo":
        return cmd_undo(args)
    if args.cmd == "journal":
        print(journal(json.loads(args.json)))
        return 0
    if args.cmd == "collect-feedback":
        return cmd_collect_feedback(args)
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
