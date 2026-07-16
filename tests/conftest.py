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
