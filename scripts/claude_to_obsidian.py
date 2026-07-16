#!/usr/bin/env python3
"""claude_to_obsidian.py — import Claude Code session transcripts into the vault.

Part of the local, $0 Personal OS memory setup. Reads Claude Code transcripts
(~/.claude/projects/<slug>/*.jsonl) and writes one readable markdown note per session
into <vault>/chats/code/. Tagging and wikilinks are 100% rule-based (keyword map +
regex) — there are NO LLM/API calls, so this costs nothing. `/mine-chats` then
distills the gold out of these imports.

Incremental: a state file (<vault>/.chat_import_state.json) maps sessionId -> source
mtime, so re-runs only process new or changed sessions. Safe to run nightly.

Usage:
  python3 claude_to_obsidian.py                # new/changed sessions, last 60 days
  python3 claude_to_obsidian.py --all          # all sessions, any age
  python3 claude_to_obsidian.py --days 14      # window override
  python3 claude_to_obsidian.py --dry-run      # report only, write nothing

Config: PERSONAL_OS_VAULT (default ~/vault).
"""
from __future__ import annotations
import argparse, json, os, re, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECTS_DIR = Path.home() / ".claude" / "projects"
VAULT = Path(os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault")))
OUT_DIR = VAULT / "chats" / "code"
STATE_FILE = VAULT / ".chat_import_state.json"
MSG_TRUNCATE = 2400          # cap a single message body
MAX_MESSAGES = 400           # cap messages rendered per session note

# Rule-based tag map: substring (lowercased) -> tag. No LLM. Generic defaults —
# extend with your own stack/domain keywords.
KEYWORD_TAG_MAP = {
    "supabase": "db", "postgres": "db", "migration": "db", "rls": "db", "sqlite": "db",
    "swift": "ios", "swiftui": "ios", "xcode": "ios", "healthkit": "ios",
    "kotlin": "android", "jetpack": "android", "compose": "android",
    "next.js": "web", "nextjs": "web", "vercel": "web", "react": "web", "tsx": "web",
    "django": "web", "flask": "web", "rails": "web",
    "graphify": "graphify", "knowledge graph": "graphify", "obsidian": "memory",
    "cron": "ops", "launchd": "ops", "systemd": "ops", "deploy": "ops", "docker": "ops",
    "ollama": "llm", "gemini": "llm", "openai": "llm", "anthropic": "llm", "claude": "llm",
    "embedding": "llm", "rag": "llm",
    "seo": "seo", "lighthouse": "seo",
}

def log(*a):
    print(*a, file=sys.stderr, flush=True)

def save_state(state: dict) -> None:
    """Atomic state write (tmp + os.replace) — an interrupt mid-write must never
    leave a torn JSON behind, or every future run would re-import everything."""
    tmp = STATE_FILE.with_name(STATE_FILE.name + ".tmp")
    tmp.write_text(json.dumps(state, indent=0))
    os.replace(tmp, STATE_FILE)

def slugify(text: str, maxlen: int = 48) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:maxlen].strip("-")) or "session"

def extract_text(content) -> str:
    """Flatten a message 'content' (str or list of blocks) into readable text.
    Tool calls collapse to a marker; tool results / thinking are dropped (noise)."""
    if isinstance(content, str):
        return content.strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for b in content:
        if isinstance(b, str):
            parts.append(b); continue
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t == "text":
            parts.append(b.get("text", ""))
        elif t == "tool_use":
            parts.append(f"_↳ tool: {b.get('name', '?')}_")
        # tool_result, thinking, image, etc. -> skipped intentionally
    return "\n".join(p for p in parts if p and p.strip()).strip()

NOISE_PREFIXES = ("<system-reminder>", "Caveat:", "<command-name>", "[Request interrupted")

def is_noise(text: str) -> bool:
    if not text:
        return True
    t = text.lstrip()
    if t.startswith(NOISE_PREFIXES):
        return True
    # pure command-message wrappers
    if t.startswith("<command-") or t.startswith("<local-command-"):
        return True
    return False

def parse_session(path: Path) -> dict | None:
    title = None
    cwd = None
    branch = None
    first_ts = None
    last_ts = None
    messages = []  # (role, text)
    with path.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                o = json.loads(line)
            except Exception:
                continue
            typ = o.get("type")
            if typ in ("custom-title", "ai-title"):
                title = o.get("customTitle") or o.get("aiTitle") or title
                continue
            if typ not in ("user", "assistant"):
                continue
            msg = o.get("message")
            if not isinstance(msg, dict):
                continue
            cwd = cwd or o.get("cwd")
            branch = branch or o.get("gitBranch")
            ts = o.get("timestamp")
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            role = msg.get("role")
            text = extract_text(msg.get("content"))
            if role == "user" and is_noise(text):
                continue
            if not text:
                continue
            if len(text) > MSG_TRUNCATE:
                text = text[:MSG_TRUNCATE] + " …[truncated]"
            messages.append((role, text))
    # need at least one real human prompt to be worth saving
    if sum(1 for r, _ in messages if r == "user") < 1:
        return None
    if not title:
        first_user = next((t for r, t in messages if r == "user"), "")
        title = first_user.splitlines()[0][:80] if first_user else path.stem[:8]
    return {
        "title": title.strip(), "cwd": cwd, "branch": branch,
        "first_ts": first_ts, "last_ts": last_ts,
        "messages": messages, "session_id": path.stem,
    }

def derive_tags(session: dict) -> list[str]:
    blob = (session["title"] + " " + " ".join(t for _, t in session["messages"][:30])).lower()
    if session.get("cwd"):
        blob += " " + session["cwd"].lower()
    tags = {"chat"}
    for needle, tag in KEYWORD_TAG_MAP.items():
        if needle in blob:
            tags.add(tag)
    return sorted(tags)

def project_name(session: dict) -> str:
    cwd = session.get("cwd") or ""
    return Path(cwd).name if cwd else "unknown"

def iso_date(ts: str | None) -> str:
    if not ts:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return ts[:10]

def render_note(session: dict, existing_notes: set[str]) -> str:
    created = iso_date(session["first_ts"])
    updated = iso_date(session["last_ts"])
    tags = derive_tags(session)
    proj = project_name(session)
    fm = [
        "---",
        f"title: {session['title']}",
        f"tags: [{', '.join(tags)}]",
        f"created: {created}",
        f"updated: {updated}",
        "status: archived",
        "type: chat",
        f"project: {proj}",
        f"session: {session['session_id'][:8]}",
        "---",
        "",
        f"# {session['title']}",
        "",
        f"> Claude Code session · project **{proj}** · branch `{session.get('branch') or '?'}` · {created}",
        "",
    ]
    # Rule-based wikilinks: link the project + any existing vault note whose stem appears in the title
    links = [f"[[{proj}]]"]
    title_l = session["title"].lower()
    for stem in existing_notes:
        if len(stem) > 4 and stem.lower() in title_l:
            links.append(f"[[{stem}]]")
    fm.append("Links: " + " · ".join(dict.fromkeys(links)))
    fm.append("")
    body = []
    for i, (role, text) in enumerate(session["messages"][:MAX_MESSAGES]):
        who = "🧑 You" if role == "user" else "🤖 Claude"
        body.append(f"### {who}")
        body.append(text)
        body.append("")
    if len(session["messages"]) > MAX_MESSAGES:
        body.append(f"_…{len(session['messages']) - MAX_MESSAGES} more messages truncated._")
    return "\n".join(fm + body) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="process all sessions regardless of age")
    ap.add_argument("--days", type=int, default=60, help="age window in days (default 60)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if not PROJECTS_DIR.exists():
        log(f"no projects dir at {PROJECTS_DIR}"); return 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    state = {}
    if STATE_FILE.exists():
        try:
            state = json.loads(STATE_FILE.read_text())
        except Exception:
            state = {}
    existing_notes = {p.stem for p in VAULT.rglob("*.md")}

    cutoff = None if args.all else (datetime.now().timestamp() - args.days * 86400)
    transcripts = sorted(PROJECTS_DIR.glob("*/*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    written = skipped = unchanged = 0
    for path in transcripts:
        mtime = path.stat().st_mtime
        if cutoff and mtime < cutoff:
            continue
        sid = path.stem
        if state.get(sid) == mtime and not args.all:
            unchanged += 1
            continue
        session = parse_session(path)
        if not session:
            skipped += 1
            state[sid] = mtime
            continue
        created = iso_date(session["first_ts"])
        proj = project_name(session)
        fname = f"{created}-{slugify(proj)}-{slugify(session['title'], 32)}-{sid[:6]}.md"
        out = OUT_DIR / fname
        if args.dry_run:
            log(f"[dry] would write {out.name} ({len(session['messages'])} msgs, tags={derive_tags(session)})")
            written += 1
            continue
        out.write_text(render_note(session, existing_notes), encoding="utf-8")
        state[sid] = mtime
        written += 1
    if not args.dry_run:
        save_state(state)
    log(f"done: {written} written, {unchanged} unchanged, {skipped} skipped (no human prompt). out={OUT_DIR}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
