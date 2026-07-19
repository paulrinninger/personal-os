"""Test wiring: make the repo's scripts/ and engine importable, isolate all state.

Every test monkeypatches module-level paths (PO, LOCK_ROOT, FIRE_LOG, VAULT, …) to
tmp_path — the suite never touches a real vault, real ~/.claude state, qmd, ollama,
or the network.
"""
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
ENGINE = os.path.join(REPO, "claude", "personal-os")
for d in (SCRIPTS, ENGINE):
    if d not in sys.path:
        sys.path.insert(0, d)


@pytest.fixture
def po_home(tmp_path, monkeypatch):
    """Redirect pos_utils' state home (locks + fire-log) into tmp_path."""
    import pos_utils
    po = tmp_path / "personal-os"
    monkeypatch.setattr(pos_utils, "PO", str(po))
    monkeypatch.setattr(pos_utils, "LOCK_ROOT", str(po / "locks"))
    monkeypatch.setattr(pos_utils, "FIRE_LOG", str(po / "lesson-fires.jsonl"))
    return po


@pytest.fixture
def autopilot_env(tmp_path, monkeypatch, po_home):
    """Redirect the pos_actions / pos_autopilot / dream state and the vault into
    tmp_path. Returns a namespace with .po (state home Path) and .vault (Path)."""
    from types import SimpleNamespace

    import dream
    import pos_actions
    import pos_autopilot

    po = str(po_home)
    po_home.mkdir(parents=True, exist_ok=True)
    vault = tmp_path / "vault"
    vault.mkdir()
    monkeypatch.setattr(pos_actions, "PO", po)
    monkeypatch.setattr(pos_actions, "JOURNAL", os.path.join(po, "actions.jsonl"))
    monkeypatch.setattr(pos_actions, "FEEDBACK", os.path.join(po, "dream-feedback.jsonl"))
    monkeypatch.setattr(pos_actions, "SCAN_STATE", os.path.join(po, "feedback-scan.json"))
    monkeypatch.setattr(pos_actions, "VAULT", str(vault))
    monkeypatch.setattr(pos_actions, "UNDONE_DIR", str(vault / "_inbox" / "_undone"))
    monkeypatch.setattr(pos_autopilot, "PO", po)
    monkeypatch.setattr(pos_autopilot, "KILL", os.path.join(po, "autopilot.off"))
    monkeypatch.setattr(pos_autopilot, "VAULT", str(vault))
    monkeypatch.setattr(pos_autopilot, "DRAFTS_DIR", str(vault / "_inbox" / "lessons"))
    monkeypatch.setattr(pos_autopilot, "REFS_DIR", str(vault / "_inbox" / "refs"))
    monkeypatch.setattr(pos_autopilot, "REFS_ARCHIVE",
                        str(vault / "_inbox" / "refs" / "_archive"))
    monkeypatch.setattr(pos_autopilot, "HQ", os.path.join(po, "harvest-queue.jsonl"))
    monkeypatch.setattr(pos_autopilot, "HQ_DONE",
                        os.path.join(po, "harvest-queue-done.jsonl"))
    monkeypatch.setattr(dream, "PO", po)
    monkeypatch.setattr(dream, "WORK_ROOT", os.path.join(po, "dream-work"))
    monkeypatch.setattr(dream, "EMBED_CACHE", os.path.join(po, "dream-embeds.json"))
    monkeypatch.setattr(dream, "FEEDBACK_FILE", os.path.join(po, "dream-feedback.jsonl"))
    monkeypatch.setattr(dream, "VAULT", str(vault))
    return SimpleNamespace(po=po_home, vault=vault)
