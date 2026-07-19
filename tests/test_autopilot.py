"""pos_autopilot.py — the tier-0 executors: act-links append+undo, the act-refs
age/status/top-N rule, the harvest garbage filter and transcript extraction,
act-dreams, the already-saved harvest drain, and the kill switch. No ollama, no
qmd, no network — scoring/LLM surfaces are monkeypatched."""
import datetime as dt
import json
import os
import time
from types import SimpleNamespace

import dream
import pos_actions
import pos_autopilot

D = dt.date.today().isoformat()


def _args(**kw):
    base = dict(date=D, dry_run=False, cap=5)
    base.update(kw)
    return SimpleNamespace(**base)


def _old(path, days=1):
    t = time.time() - days * 86400
    os.utime(path, (t, t))


def _write_pass(env, name, data):
    wd = os.path.join(dream.WORK_ROOT, D)
    os.makedirs(wd, exist_ok=True)
    with open(os.path.join(wd, name + ".json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _note(env, rel, body="body text\n"):
    p = env.vault / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntitle: {p.stem}\n---\n\n{body}")
    _old(p, days=1)  # past the 30-min mtime guard
    return p


# ---------------------------------------------------------------- act-links
def test_act_links_appends_reciprocally_and_undo_roundtrips(autopilot_env):
    a = _note(autopilot_env, "lessons/alpha.md", "body\n\n## Links\n- [[old]]\n")
    b = _note(autopilot_env, "knowledge/beta.md")
    orig_a, orig_b = a.read_text(), b.read_text()
    _write_pass(autopilot_env, "connections", {"suggestions": [
        {"a": "lessons/alpha.md", "b": "knowledge/beta.md", "score": 90, "snippet": "s"}]})
    pos_autopilot.cmd_act_links(_args())
    ta, tb = a.read_text(), b.read_text()
    assert "- [[beta]] — auto-link" in ta
    assert "- [[alpha]] — auto-link" in tb
    # inserted under the existing ## Links heading, not dangling at EOF
    assert ta.index("## Links") < ta.index("[[beta]]")
    rows = pos_actions._read_journal()
    assert rows and rows[-1]["action"] == "link.add"
    pos_actions.cmd_undo(SimpleNamespace(last=None, night=D, id=None, dry_run=False))
    assert a.read_text() == orig_a and b.read_text() == orig_b


def test_act_links_respects_threshold_curated_mtime_and_existing_links(autopilot_env):
    lo = _note(autopilot_env, "lessons/low.md")
    hi = _note(autopilot_env, "lessons/high.md")
    fresh = _note(autopilot_env, "lessons/fresh.md")
    os.utime(fresh)  # touched right now -> concurrent-edit guard
    inbox = _note(autopilot_env, "_inbox/lessons/card.md")
    linked_a = _note(autopilot_env, "lessons/linked-a.md", "x [[linked-b]] y\n")
    linked_b = _note(autopilot_env, "lessons/linked-b.md")
    _write_pass(autopilot_env, "connections", {"suggestions": [
        {"a": "lessons/low.md", "b": "lessons/high.md", "score": 60},        # below 75
        {"a": "lessons/high.md", "b": "lessons/fresh.md", "score": 90},      # mtime guard
        {"a": "lessons/high.md", "b": "_inbox/lessons/card.md", "score": 90},  # not curated
        {"a": "lessons/linked-a.md", "b": "lessons/linked-b.md", "score": 90},  # already linked
    ]})
    pos_autopilot.cmd_act_links(_args())
    for p in (lo, hi, fresh, inbox, linked_b):
        assert "auto-link" not in p.read_text()
    assert pos_actions._read_journal() == []


def test_act_links_cap(autopilot_env, monkeypatch):
    monkeypatch.setattr(pos_autopilot, "LINK_CAP", 2)
    notes = [_note(autopilot_env, f"lessons/n{i}.md") for i in range(6)]
    _write_pass(autopilot_env, "connections", {"suggestions": [
        {"a": f"lessons/n{i}.md", "b": f"lessons/n{i + 3}.md", "score": 90 - i}
        for i in range(3)]})
    pos_autopilot.cmd_act_links(_args())
    assert len(pos_actions._read_journal()) == 2
    assert "auto-link" not in notes[2].read_text()  # lowest score lost to the cap


def test_kill_switch_stops_execution(autopilot_env):
    a = _note(autopilot_env, "lessons/k.md")
    _write_pass(autopilot_env, "connections", {"suggestions": [
        {"a": "lessons/k.md", "b": "lessons/k.md", "score": 99}]})
    open(pos_autopilot.KILL, "w").close()
    pos_autopilot.cmd_act_links(_args())
    assert "auto-link" not in a.read_text()
    assert pos_actions._read_journal() == []


# ---------------------------------------------------------------- act-dreams
def test_act_dreams_supersedes_only_old_drafts(autopilot_env):
    dreams = autopilot_env.vault / "_inbox" / "dreams"
    dreams.mkdir(parents=True)
    old = dreams / "2026-01-01-dream.md"
    old.write_text("---\nstatus: draft\n---\nold\n")
    recent = dreams / f"{D}-dream.md"
    recent.write_text("---\nstatus: draft\n---\nnew\n")
    journal = dreams / "2026-01-02-dream.md"
    journal.write_text("---\nstatus: journal\n---\nx\n")
    pos_autopilot.cmd_act_dreams(_args())
    assert "status: superseded" in old.read_text()
    assert "status: draft" in recent.read_text()      # inside the 3-day window
    assert "status: journal" in journal.read_text()   # journals are never touched
    rows = pos_actions._read_journal()
    assert len(rows) == 1 and rows[0]["action"] == "note.status"


# ----------------------------------------------------------------- act-refs
def _card(env, name, status, age_days):
    p = env.vault / "_inbox" / "refs" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    fm = f"---\nstatus: {status}\n---\n\n" if status else "---\ntype: ref\n---\n\n"
    p.write_text(fm + "card\n")
    _old(p, days=age_days)
    return p


def _scored(env, names):
    return [{"card": f"_inbox/refs/{n}", "path": str(env.vault / "_inbox" / "refs" / n),
             "hub": "hub", "score": round(0.9 - i * 0.1, 3)}
            for i, n in enumerate(names)]


def test_act_refs_age_status_topn_rule(autopilot_env, monkeypatch):
    monkeypatch.setattr(pos_autopilot, "KEEP_TOP", 1)
    top = _card(autopilot_env, "top.md", "inbox", 40)        # rank 0 -> kept (top-N)
    stale = _card(autopilot_env, "stale.md", "inbox", 40)    # rank 1, old -> ARCHIVED
    young = _card(autopilot_env, "young.md", "parked", 5)    # rank 2, too young -> kept
    foreign = _card(autopilot_env, "foreign.md", "", 40)     # no inbox/parked status -> kept
    monkeypatch.setattr(dream, "ollama_up", lambda: True)
    monkeypatch.setattr(pos_autopilot, "_active_hub_vecs",
                        lambda: [{"name": "hub", "vec": [1.0]}])
    monkeypatch.setattr(pos_autopilot, "_score_refs_cards",
                        lambda cards, hubs, max_new_embeds=200:
                        (_scored(autopilot_env,
                                 ["top.md", "stale.md", "young.md", "foreign.md"]), 0, 0))
    pos_autopilot.cmd_act_refs(_args())
    archive = autopilot_env.vault / "_inbox" / "refs" / "_archive"
    assert (archive / "stale.md").exists() and not stale.exists()
    for p in (top, young, foreign):
        assert p.exists()
    rows = pos_actions._read_journal()
    assert len(rows) == 1 and rows[0]["action"] == "card.archive"
    assert rows[0]["undo"] == {"op": "move", "from": str(stale),
                               "to": str(archive / "stale.md")}


def test_act_refs_dry_run_moves_nothing(autopilot_env, monkeypatch):
    monkeypatch.setattr(pos_autopilot, "KEEP_TOP", 0)
    stale = _card(autopilot_env, "s.md", "inbox", 40)
    monkeypatch.setattr(dream, "ollama_up", lambda: True)
    monkeypatch.setattr(pos_autopilot, "_active_hub_vecs",
                        lambda: [{"name": "hub", "vec": [1.0]}])
    monkeypatch.setattr(pos_autopilot, "_score_refs_cards",
                        lambda cards, hubs, max_new_embeds=200:
                        (_scored(autopilot_env, ["s.md"]), 0, 0))
    pos_autopilot.cmd_act_refs(_args(dry_run=True))
    assert stale.exists()
    assert pos_actions._read_journal() == []


def test_act_refs_skips_without_ollama(autopilot_env, monkeypatch):
    stale = _card(autopilot_env, "s2.md", "inbox", 40)
    monkeypatch.setattr(dream, "ollama_up", lambda: False)
    pos_autopilot.cmd_act_refs(_args())
    assert stale.exists() and pos_actions._read_journal() == []


# --------------------------------------------------- harvest: filter + text
def test_garbage_title_filter_en_and_de():
    garbage = [
        "It seems the conversation covered several topics",
        "The assistant helped with a refactor",
        "This session was about fixing tests",
        "Here is a summary of the chat",
        "Summary of the changes made",
        "Unfortunately there is no clear lesson",
        "Es scheint um ein Refactoring zu gehen",
        "Die Konversation drehte sich um Tests",
        "Zusammenfassung: viel passiert",
        "Hier ist eine Übersicht",
    ]
    legit = [
        "Always fetch before diagnosing a repo",
        "Never pipe deploy CLIs through tail",
        "Run the full tsc, not tsconfig.app.json",
        "Nie Deploys annehmen — aktiv verifizieren",
    ]
    for t in garbage:
        assert pos_autopilot.GARBAGE_TITLE.search(t), t
    for t in legit:
        assert not pos_autopilot.GARBAGE_TITLE.search(t), t


def test_transcript_text_extraction_and_truncation():
    lines = [
        json.dumps({"message": {"content": "plain user text"}}),
        json.dumps({"message": {"content": [
            {"type": "text", "text": "assistant text block"},
            {"type": "tool_use", "name": "Bash", "input": {"command": "rm -rf /tmp/x"}},
        ]}}),
        "{ not json at all",
        json.dumps({"type": "progress"}),  # no message
    ]
    out = pos_autopilot._transcript_text("\n".join(lines))
    assert "plain user text" in out
    assert "assistant text block" in out
    assert "rm -rf" not in out  # tool payloads stay out of the judge prompt
    assert pos_autopilot._transcript_text("\n".join(lines), max_chars=10) == out[-10:]


def test_is_no_matches_no_but_not_note():
    assert pos_autopilot._is_no("NO: plain feature work")
    assert pos_autopilot._is_no("no lesson here")
    assert not pos_autopilot._is_no("YES: always do X")
    assert not pos_autopilot._is_no("Note the fix applied")


# ----------------------------------------------- act-harvest (no-LLM paths)
def test_act_harvest_already_saved_drains_and_requeues_on_undo(autopilot_env, monkeypatch, tmp_path):
    tp = tmp_path / "transcript.jsonl"
    vb = os.path.basename(str(autopilot_env.vault))
    tp.write_text(json.dumps({"message": {"content": "did things"}}) + "\n"
                  + '{"toolu":"x","input":{"file_path":"/home/u/' + vb
                  + '/logs/2026-01-01-x.md"}}\n')
    entry = {"session_id": "s1", "transcript_path": str(tp), "cwd": "/x", "ts": "t"}
    orig_q = json.dumps(entry, ensure_ascii=False) + "\n"
    with open(pos_autopilot.HQ, "w", encoding="utf-8") as f:
        f.write(orig_q)
    monkeypatch.setattr(dream, "ollama_up", lambda: False)  # already-saved needs no LLM
    pos_autopilot.cmd_act_harvest(_args())
    assert open(pos_autopilot.HQ, encoding="utf-8").read() == ""
    done = [json.loads(l) for l in open(pos_autopilot.HQ_DONE, encoding="utf-8")]
    assert done[0]["reason"] == "already-saved" and done[0]["session_id"] == "s1"
    rows = pos_actions._read_journal()
    assert rows[-1]["action"] == "queue.done"
    pos_actions.cmd_undo(SimpleNamespace(last=None, night=D, id=None, dry_run=False))
    assert open(pos_autopilot.HQ, encoding="utf-8").read() == orig_q
    assert open(pos_autopilot.HQ_DONE, encoding="utf-8").read() == ""


def test_act_harvest_without_llm_leaves_unsaved_sessions_queued(autopilot_env,
                                                                monkeypatch, tmp_path):
    tp = tmp_path / "t2.jsonl"
    tp.write_text(json.dumps({"message": {"content": "no save happened"}}) + "\n")
    entry = {"session_id": "s2", "transcript_path": str(tp), "cwd": "/x", "ts": "t"}
    with open(pos_autopilot.HQ, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    monkeypatch.setattr(dream, "ollama_up", lambda: False)
    pos_autopilot.cmd_act_harvest(_args())
    # LLM needed but down -> batch aborted, queue untouched, nothing journaled
    assert json.loads(open(pos_autopilot.HQ, encoding="utf-8").read())["session_id"] == "s2"
    assert pos_actions._read_journal() == []


def test_act_harvest_gone_transcript_is_checked_off(autopilot_env, monkeypatch):
    entry = {"session_id": "s3", "transcript_path": "/nonexistent/t.jsonl",
             "cwd": "/x", "ts": "t"}
    with open(pos_autopilot.HQ, "w", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    monkeypatch.setattr(dream, "ollama_up", lambda: False)
    pos_autopilot.cmd_act_harvest(_args())
    done = [json.loads(l) for l in open(pos_autopilot.HQ_DONE, encoding="utf-8")]
    assert done[0]["reason"] == "transcript-gone"
    assert open(pos_autopilot.HQ, encoding="utf-8").read() == ""
