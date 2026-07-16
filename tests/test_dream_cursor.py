"""dream.py `_yesterday_docs` — the chats cursor must be FIFO and must never skip
an unconsumed backlog file (the v0.2 bug: sort(reverse) + cursor=max over ALL new
chats permanently dropped everything beyond the cap)."""
import json
import os
import time
import types

import pytest

import dream

DATE = "2026-01-02"          # "today" for the pass; yesterday = 2026-01-01
YESTERDAY = "2026-01-01"


def args():
    return types.SimpleNamespace(date=DATE, force=False)


@pytest.fixture
def vault(tmp_path, monkeypatch):
    v = tmp_path / "vault"
    (v / "chats" / "code").mkdir(parents=True)
    (v / "logs").mkdir(parents=True)
    monkeypatch.setattr(dream, "VAULT", str(v))
    monkeypatch.setattr(dream, "CURSOR_FILE", str(tmp_path / "dream-cursor.json"))
    return v


def make_chats(vault, n, base):
    """n chat files with strictly increasing mtimes base+10, base+20, …"""
    files = []
    for i in range(1, n + 1):
        f = vault / "chats" / "code" / f"chat-{i:02d}.md"
        f.write_text(f"chat {i}", encoding="utf-8")
        os.utime(f, (base + 10 * i, base + 10 * i))
        files.append(str(f))
    return files


def set_cursor(path, value):
    with open(path, "w") as f:
        json.dump({"chats_mtime": value}, f)


def test_backlog_larger_than_room_never_skips_unconsumed(vault, tmp_path):
    base = time.time() - 3600
    chats = make_chats(vault, 5, base)
    set_cursor(str(tmp_path / "dream-cursor.json"), base)

    docs, cursor = dream._yesterday_docs(args(), cap=2)

    # FIFO: the two OLDEST new chats are consumed first
    assert docs == [chats[0], chats[1]]
    # the cursor stops at the last CONSUMED file — chats 3..5 stay eligible
    assert cursor == os.path.getmtime(chats[1])
    assert cursor < os.path.getmtime(chats[2])


def test_next_run_picks_up_where_the_last_stopped(vault, tmp_path):
    base = time.time() - 3600
    chats = make_chats(vault, 5, base)
    cursor_file = str(tmp_path / "dream-cursor.json")
    set_cursor(cursor_file, base)

    _, cursor = dream._yesterday_docs(args(), cap=2)
    set_cursor(cursor_file, cursor)  # simulate the pass committing its cursor
    docs2, cursor2 = dream._yesterday_docs(args(), cap=2)

    assert docs2 == [chats[2], chats[3]]           # backlog drains in order
    assert cursor2 == os.path.getmtime(chats[3])


def test_logs_fill_cap_leaves_cursor_untouched(vault, tmp_path):
    base = time.time() - 3600
    make_chats(vault, 3, base)
    set_cursor(str(tmp_path / "dream-cursor.json"), base)
    for i in range(2):
        (vault / "logs" / f"{YESTERDAY}-session-{i}.md").write_text("log", encoding="utf-8")

    docs, cursor = dream._yesterday_docs(args(), cap=2)

    assert len(docs) == 2 and all("logs" in d for d in docs)
    assert cursor == base                          # nothing consumed -> cursor unchanged


def test_no_chats_no_cursor_file_defaults(vault):
    (vault / "logs" / f"{YESTERDAY}-only-log.md").write_text("log", encoding="utf-8")

    docs, cursor = dream._yesterday_docs(args(), cap=5)

    assert len(docs) == 1 and docs[0].endswith("only-log.md")
    # default cursor = "roughly 24h ago", a float, and no crash without state
    assert isinstance(cursor, float)
    assert cursor <= time.time()
