"""The ventures/producer passes: registration doesn't break the core engine, and the
offline-capable parts (producer templating + queue drain, ventures no-hub skip) work
without ollama/qmd/network."""
import json
import types

import pytest

import dream


def args():
    return types.SimpleNamespace(date="2026-01-02", force=False)


def test_all_passes_registered():
    # every pass has baseline params AND a cmd_ function; the report assembler and
    # cursor logic import cleanly alongside them (this module importing at all is
    # half the test)
    for name in ("fires", "gc", "connections", "residue", "triage", "ventures", "producer"):
        assert name in dream.DEFAULTS
    for fn in ("cmd_fires", "cmd_gc_digest", "cmd_connections", "cmd_residue",
               "cmd_triage", "cmd_ventures", "cmd_producer", "cmd_report"):
        assert callable(getattr(dream, fn))


def test_adaptive_params_producer_reads_its_own_channel(tmp_path, monkeypatch):
    # producer feedback lives in its OWN file so accepted/rejected drafts don't skew
    # the other passes' thresholds (published bug-audit fix — keep it covered)
    dream_fb = tmp_path / "dream-feedback.jsonl"
    prod_fb = tmp_path / "producer-feedback.jsonl"
    monkeypatch.setattr(dream, "FEEDBACK_FILE", str(dream_fb))
    monkeypatch.setattr(dream, "PRODUCER_FEEDBACK_FILE", str(prod_fb))
    with open(prod_fb, "w") as f:
        for _ in range(10):
            f.write(json.dumps({"pass": "producer", "verdict": "accepted"}) + "\n")
    p = dream.adaptive_params("producer")
    assert p["_acceptance"] == 1.0          # read from producer-feedback.jsonl
    assert "_acceptance" not in dream.adaptive_params("fires")  # dream channel is empty


@pytest.fixture
def producer_env(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    drafts = vault / "_inbox" / "producer-drafts"
    monkeypatch.setattr(dream, "VAULT", str(vault))
    monkeypatch.setattr(dream, "WORK_ROOT", str(tmp_path / "dream-work"))
    monkeypatch.setattr(dream, "PRODUCER_QUEUE", str(tmp_path / "producer-queue.jsonl"))
    monkeypatch.setattr(dream, "PRODUCER_TEMPLATES", str(tmp_path / "producer-templates.json"))
    monkeypatch.setattr(dream, "PRODUCER_FEEDBACK_FILE", str(tmp_path / "producer-feedback.jsonl"))
    monkeypatch.setattr(dream, "PRODUCER_DRAFTS_DIR", str(drafts))
    return tmp_path, drafts


def test_producer_renders_and_drains_queue_offline(producer_env):
    tmp_path, drafts = producer_env
    with open(tmp_path / "producer-templates.json", "w") as f:
        json.dump({"pb": "Hi {name}, {observation} {pain_point} {cta}"}, f)
    complete = {"id": "lead-001", "playbook": "pb",
                "lead": {"name": "Jane", "company": "Acme",
                         "observation": "obs text", "pain_point": "pain text"},
                "cta": "call?"}
    incomplete = {"id": "lead-002", "playbook": "pb",
                  "lead": {"name": "Joe", "company": "Beta"}}  # no observation/pain_point
    with open(tmp_path / "producer-queue.jsonl", "w") as f:
        f.write(json.dumps(complete) + "\n")
        f.write(json.dumps(incomplete) + "\n")

    dream.cmd_producer(args())               # pure templating: no ollama, no network

    files = list(drafts.glob("*.md"))
    assert len(files) == 1
    text = files[0].read_text(encoding="utf-8")
    assert "obs text" in text and "pain text" in text
    assert "DRAFT ONLY" in text
    # queue drained: the rendered entry is gone, the incomplete one stays for fixing
    remaining = [json.loads(l) for l in open(tmp_path / "producer-queue.jsonl") if l.strip()]
    assert [e["id"] for e in remaining] == ["lead-002"]
    state = json.load(open(tmp_path / "dream-work" / "2026-01-02" / "producer.json"))
    assert state["queue_remaining"] == 1 and state["incomplete"] == 1
    assert state["drafts"][0]["lead_company"] == "Acme"


def test_producer_missing_id_is_never_rendered(producer_env):
    tmp_path, drafts = producer_env
    with open(tmp_path / "producer-templates.json", "w") as f:
        json.dump({"pb": "Hi {name}"}, f)
    no_id = {"playbook": "pb", "lead": {"name": "X", "observation": "o", "pain_point": "p"}}
    with open(tmp_path / "producer-queue.jsonl", "w") as f:
        f.write(json.dumps(no_id) + "\n")
    dream.cmd_producer(args())
    assert list(drafts.glob("*.md")) == []   # id required for safe queue-drain


def test_ventures_skips_without_hubs_and_without_ollama(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    monkeypatch.setattr(dream, "VAULT", str(vault))
    monkeypatch.setattr(dream, "WORK_ROOT", str(tmp_path / "dream-work"))
    monkeypatch.setattr(dream, "VENTURES_CURSOR", str(tmp_path / "ventures-cursor.json"))
    monkeypatch.setattr(dream, "VENTURES_EMBEDS", str(tmp_path / "ventures-embeds.json"))
    monkeypatch.setattr(dream, "FEEDBACK_FILE", str(tmp_path / "dream-feedback.jsonl"))

    dream.cmd_ventures(args())               # no hubs -> skip before any ollama call

    state = json.load(open(tmp_path / "dream-work" / "2026-01-02" / "ventures.json"))
    assert state["skipped"] == "no project hubs"
