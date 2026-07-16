#!/usr/bin/env python3
"""chatgpt_to_obsidian.py — import a ChatGPT data export (zip) into the vault.

Sibling of claude_to_obsidian.py (Claude Code transcripts). Reads conversations-*.json
directly out of a ChatGPT data-export zip via zipfile (no extraction needed — the zip
is typically 1-2 GB, the JSON shards inside only a fraction of that) and writes one
readable markdown note per conversation into <vault>/chats/gpt/. Tagging and wikilinks
are 100% rule-based (keyword map + regex) — NO LLM/API calls, $0.

This is a manual, one-off import (run it once per export you download from
chatgpt.com/#settings → Data controls → Export), not part of the nightly scheduler.
After conversion, `/mine-chats` (extended to also watch chats/gpt/) distills the gold
out of it into lessons/ideas/knowledge/profile — same review-gated flow as any other
chat import.

Export format notes (verified against a 2026 export; ChatGPT's export format has
changed before and may change again):
- mapping nodes carry only {id, message, parent} — NO children arrays. The canonical
  thread is recovered by walking parent pointers from current_node to the root and
  reversing; abandoned regeneration branches fall away automatically.
- content_type 'thoughts' / 'reasoning_recap' are model thinking traces -> dropped as noise.
- Voice chats carry their words in dict parts {content_type: audio_transcription, text}.
- Image parts carry an asset_pointer 'file-service://file-XXX' -> file-XXX.dat in the
  zip; conversation_asset_file_names.json maps that to the original upload filename.
  We render a placeholder only — assets stay in the zip; retrieve on demand later via
  `unzip -p <export.zip> file-XXX.dat`.

Incremental: a state file (<vault>/.chatgpt_import_state.json) maps conversation_id ->
{"updated": <update_time>, "file": <note name>}; re-runs rewrite only changed convs, so
you can re-run this against a newer export and only get the delta.

PRIVACY: your ChatGPT history is often more personal than coding transcripts (health,
finances, relationships). The vault scaffold's .gitignore already excludes chats/
entirely (raw imports never reach a remote) — keep it that way if you maintain your
own ignore rules. The distilled notes that /mine-chats produces are what should end
up versioned.

Usage:
  python3 chatgpt_to_obsidian.py --zip ~/Downloads/chatgpt-export.zip --dry-run
  python3 chatgpt_to_obsidian.py --zip <zip>                    # real import
  python3 chatgpt_to_obsidian.py --zip <zip> --manifest out.jsonl   # also emit a
                                                                     # per-conversation
                                                                     # manifest (useful
                                                                     # if you want to
                                                                     # batch-mine it)

Config: PERSONAL_OS_VAULT (default ~/vault).
"""
from __future__ import annotations
import argparse, fnmatch, json, os, re, sys, zipfile
from datetime import datetime
from pathlib import Path

VAULT = Path(os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault")))
OUT_DIR = VAULT / "chats" / "gpt"
STATE_FILE = VAULT / ".chatgpt_import_state.json"
MSG_TRUNCATE = 4000          # higher than code chats: pasted docs/plans are mining signal
MAX_MESSAGES = 600           # long-running conversations can run into the hundreds of turns

DROP_CONTENT_TYPES = {"thoughts", "reasoning_recap"}
DROP_ROLES = {"system", "tool"}

# Rule-based tag map: substring (lowercased) -> tag. No LLM. Generic defaults —
# extend with your own stack/domain keywords, same idea as claude_to_obsidian.py's map.
KEYWORD_TAG_MAP = {
    "supabase": "db", "postgres": "db", "sqlite": "db", "migration": "db",
    "shopify": "ecommerce", "stripe": "ecommerce", "checkout": "ecommerce",
    "tax": "finance", "accounting": "finance", "bookkeeping": "finance",
    "next.js": "web", "nextjs": "web", "vercel": "web", "react": "web",
    "seo": "seo", "lighthouse": "seo",
    "ollama": "llm", "gemini": "llm", "openai": "llm", "claude": "llm", "anthropic": "llm",
    "marketing": "marketing", "positioning": "marketing", "pricing": "business",
    "invoice": "business", "business plan": "business", "investor": "business",
    "instagram": "content", "tiktok": "content", "youtube": "content", "hook": "content",
    "video edit": "video", "premiere": "video", "davinci": "video",
    "camera": "photo", "lens": "photo", "photoshoot": "photo",
    "travel": "travel", "flight": "travel", "hotel": "travel",
    "macos": "ops", "launchd": "ops", "homebrew": "ops",
}

def log(*a):
    print(*a, file=sys.stderr, flush=True)

def save_state(state: dict) -> None:
    """Atomic state write (tmp + os.replace) — an interrupt mid-write must never
    leave a torn JSON behind, or the next run would re-import everything."""
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=0))
    os.replace(tmp, STATE_FILE)

def slugify(text: str, maxlen: int = 48) -> str:
    s = (text or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return (s[:maxlen].strip("-")) or "conversation"

def yaml_str(s: str) -> str:
    s = " ".join((s or "").split())
    if any(c in s for c in ':#"{}[]&*?|>!%@`') or s != s.strip():
        return '"' + s.replace('"', "'") + '"'
    return s

def ts_date(ts) -> str:
    try:
        return datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except Exception:
        return "1970-01-01"

def canonical_nodes(conv: dict) -> list[dict]:
    """Walk parent pointers from current_node to root, return nodes in thread order."""
    mapping = conv.get("mapping") or {}
    node_id = conv.get("current_node")
    chain, seen = [], set()
    while node_id and node_id in mapping and node_id not in seen:
        seen.add(node_id)
        node = mapping[node_id]
        chain.append(node)
        node_id = node.get("parent")
    chain.reverse()
    return chain

def part_text(part, asset_names: dict) -> str:
    if isinstance(part, str):
        return part.strip()
    if not isinstance(part, dict):
        return ""
    ct = part.get("content_type")
    if ct == "audio_transcription":
        return (part.get("text") or "").strip()
    if ct == "image_asset_pointer":
        pointer = (part.get("asset_pointer") or "").rsplit("/", 1)[-1]
        name = asset_names.get(pointer + ".dat") or asset_names.get(pointer) or pointer or "upload"
        return f"_[image: {name}]_"
    # audio/video asset pointers etc. — no renderable text content
    return ""

def message_text(msg: dict, asset_names: dict) -> str:
    content = msg.get("content") or {}
    ct = content.get("content_type")
    if ct in DROP_CONTENT_TYPES:
        return ""
    if ct == "code":
        code = (content.get("text") or "").strip()
        return f"```\n{code}\n```" if code else ""
    parts = content.get("parts")
    if not isinstance(parts, list):
        return ""
    out = [part_text(p, asset_names) for p in parts]
    return "\n".join(t for t in out if t).strip()

def parse_conversation(conv: dict, asset_names: dict) -> dict | None:
    if conv.get("is_do_not_remember"):
        return None
    messages = []  # (role, text)
    for node in canonical_nodes(conv):
        msg = node.get("message")
        if not isinstance(msg, dict):
            continue
        role = (msg.get("author") or {}).get("role")
        if role in DROP_ROLES or role not in ("user", "assistant"):
            continue
        if (msg.get("metadata") or {}).get("is_visually_hidden_from_conversation"):
            continue
        text = message_text(msg, asset_names)
        if not text:
            continue
        if len(text) > MSG_TRUNCATE:
            text = text[:MSG_TRUNCATE] + " …[truncated]"
        messages.append((role, text))
    if sum(1 for r, _ in messages if r == "user") < 1:
        return None
    cid = conv.get("conversation_id") or conv.get("id") or ""
    title = " ".join((conv.get("title") or "").split()).strip()
    if not title:
        first_user = next((t for r, t in messages if r == "user"), "")
        title = first_user.splitlines()[0][:80] if first_user else cid[:8]
    return {
        "id": cid,
        "title": title[:120],
        "created": ts_date(conv.get("create_time")),
        "updated": ts_date(conv.get("update_time") or conv.get("create_time")),
        "update_time": float(conv.get("update_time") or conv.get("create_time") or 0),
        "model": conv.get("default_model_slug") or "?",
        "voice": bool(conv.get("voice")),
        "archived": bool(conv.get("is_archived")),
        "starred": bool(conv.get("is_starred")),
        "gizmo": bool(conv.get("conversation_template_id")),
        "messages": messages,
    }

def derive_tags(c: dict) -> list[str]:
    blob = (c["title"] + " " + " ".join(t for _, t in c["messages"][:30])).lower()
    tags = {"chat", "gpt"}
    for needle, tag in KEYWORD_TAG_MAP.items():
        if needle in blob:
            tags.add(tag)
    return sorted(tags)

def render_note(c: dict, existing_notes: set[str]) -> str:
    tags = derive_tags(c)
    fm = [
        "---",
        f"title: {yaml_str(c['title'])}",
        f"tags: [{', '.join(tags)}]",
        f"created: {c['created']}",
        f"updated: {c['updated']}",
        "status: archived",
        "type: chat",
        "source: chatgpt",
        f"model: {c['model']}",
        f"conversation: {c['id'][:8]}",
    ]
    for flag in ("voice", "archived", "starred", "gizmo"):
        if c[flag]:
            fm.append(f"{flag}: true")
    fm += ["---", "", f"# {c['title']}", ""]
    marks = [m for m, on in (("voice", c["voice"]), ("custom GPT", c["gizmo"]),
                             ("archived", c["archived"])) if on]
    sub = f"> ChatGPT conversation · model `{c['model']}` · {c['created']}"
    if marks:
        sub += " · " + ", ".join(marks)
    fm += [sub, ""]
    title_l = c["title"].lower()
    links = [f"[[{stem}]]" for stem in existing_notes if len(stem) > 4 and stem.lower() in title_l]
    if links:
        fm += ["Links: " + " · ".join(dict.fromkeys(links)), ""]
    body = []
    for role, text in c["messages"][:MAX_MESSAGES]:
        body.append("### 🧑 you" if role == "user" else "### 🤖 ChatGPT")
        body.append(text)
        body.append("")
    if len(c["messages"]) > MAX_MESSAGES:
        body.append(f"_…{len(c['messages']) - MAX_MESSAGES} more messages truncated._")
    return "\n".join(fm + body) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", required=True, help="path to the ChatGPT data-export zip")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--manifest", help="write a jsonl manifest covering ALL parsed conversations")
    args = ap.parse_args()

    zpath = Path(args.zip).expanduser()
    if not zpath.exists():
        log(f"zip not found: {zpath}"); return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}
    existing_notes = {p.stem for p in VAULT.rglob("*.md")
                      if not str(p).startswith(str(OUT_DIR))}

    written = unchanged = skipped = 0
    manifest_rows = []
    with zipfile.ZipFile(zpath) as zf:
        asset_names = {}
        try:
            asset_names = json.loads(zf.read("conversation_asset_file_names.json"))
        except Exception:
            log("note: no asset filename manifest in this export (older format?)")
        shards = sorted(n for n in zf.namelist() if fnmatch.fnmatch(n, "conversations*.json"))
        if not shards:
            log("no conversations*.json in zip — is this a ChatGPT data export?"); return 1
        for shard in shards:
            with zf.open(shard) as f:
                data = json.load(f)
            for conv in data:
                cid = conv.get("conversation_id") or conv.get("id") or ""
                prev = state.get(cid)
                upd = float(conv.get("update_time") or conv.get("create_time") or 0)
                if prev and prev.get("updated", 0) >= upd and not args.manifest:
                    unchanged += 1
                    continue
                c = parse_conversation(conv, asset_names)
                if not c:
                    skipped += 1
                    if not args.dry_run:
                        state[cid] = {"updated": upd, "file": None}
                    continue
                # id tail, not head: ChatGPT conversation ids are time-ordered, so
                # same-day conversations can share their leading hex; the tail carries
                # the actual entropy — use it for a collision-free short id.
                fname = f"{c['created']}-{slugify(c['title'])}-{c['id'][-6:]}.md"
                if args.manifest:
                    manifest_rows.append({
                        "conv_id": c["id"], "file": str(OUT_DIR / fname),
                        "date": c["created"], "title": c["title"],
                        "user_chars": sum(len(t) for r, t in c["messages"] if r == "user"),
                        "total_chars": sum(len(t) for _, t in c["messages"]),
                        "n_msgs": len(c["messages"]), "tags": derive_tags(c),
                        "model": c["model"], "voice": c["voice"],
                    })
                if prev and prev.get("updated", 0) >= upd:
                    unchanged += 1
                    continue
                if args.dry_run:
                    written += 1
                    continue
                if prev and prev.get("file") and prev["file"] != fname:
                    old = OUT_DIR / prev["file"]
                    if old.exists():
                        old.unlink()
                OUT_DIR.joinpath(fname).write_text(render_note(c, existing_notes), encoding="utf-8")
                state[cid] = {"updated": upd, "file": fname}
                written += 1
            log(f"  {shard}: done (written so far: {written})")
    if not args.dry_run:
        save_state(state)
    if args.manifest:
        with open(args.manifest, "w", encoding="utf-8") as mf:
            for row in manifest_rows:
                mf.write(json.dumps(row, ensure_ascii=False) + "\n")
        log(f"manifest: {len(manifest_rows)} rows -> {args.manifest}")
    log(f"done: {written} written, {unchanged} unchanged, {skipped} skipped (no user msg / do-not-remember). out={OUT_DIR}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
