#!/usr/bin/env python3
"""qmd_search.py — THE one qmd client for hooks, dream engine and doctor ($0, stdlib).

Replaces four divergent hand-rolled parsers of qmd's text output with
`qmd vsearch --format json`. The score arrives as a 0–1 float and is normalized to
a 0–100 int so the existing thresholds (58 in the hooks, 75 in the connections pass)
keep their meaning.

vsearch() NEVER raises — the result is always:
  {"hits": [...], "outcome": "ok"|"timeout"|"error"|"no_qmd", "error": "<short>"}
hit = {"path": "lessons/foo.md" (vault-relative), "abs_path": "/…/lessons/foo.md"|None,
       "docid": "997aea", "score": 0-100, "line": int|None, "title": str, "snippet": str}

Config (env, optional): PERSONAL_OS_VAULT — vault location (default ~/vault).
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess

VAULT = os.path.expanduser(os.environ.get("PERSONAL_OS_VAULT", "~/vault"))

_SNIPPET_SKIP = ("@@", "---", "Title:", "##", "title:", "tags:", "created:",
                 "updated:", "status:", "type:", "confidence:", "review_by:")


def _qmd_bin() -> str | None:
    p = shutil.which("qmd") or "/opt/homebrew/bin/qmd"
    return p if os.path.exists(p) else None


def _clean_snippet(raw: str) -> str:
    """First content-bearing line of the qmd snippet (hunk headers / frontmatter
    stripped). Fallback: the note title from the frontmatter `title:` line — better
    than empty when the hit lands inside the frontmatter block."""
    title_fallback = ""
    for line in (raw or "").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("title:") and not title_fallback:
            title_fallback = s[len("title:"):].strip().strip('"')[:200]
        if any(s.startswith(k) for k in _SNIPPET_SKIP):
            continue
        if s.startswith("- ") or len(s) > 8:
            return s[:200]
    return title_fallback


def vsearch(query: str, n: int = 5, timeout: float = 9) -> dict:
    qmd = _qmd_bin()
    if not qmd:
        return {"hits": [], "outcome": "no_qmd", "error": "qmd binary not found"}
    try:
        proc = subprocess.run(
            [qmd, "vsearch", query, "-n", str(n), "--format", "json"],
            capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"hits": [], "outcome": "timeout", "error": f"timeout {timeout}s"}
    except Exception as e:
        return {"hits": [], "outcome": "error", "error": str(e)[:120]}
    try:
        raw = json.loads(proc.stdout or "[]")
    except Exception as e:
        return {"hits": [], "outcome": "error", "error": "bad json: " + str(e)[:100]}
    hits = []
    for r in raw if isinstance(raw, list) else []:
        f = str(r.get("file") or "")
        path = f[len("qmd://"):] if f.startswith("qmd://") else f
        try:
            score = int(round(float(r.get("score") or 0) * 100))
        except (TypeError, ValueError):
            score = 0
        ap = os.path.join(VAULT, path)
        hits.append({
            "path": path,
            "abs_path": ap if os.path.exists(ap) else None,
            "docid": str(r.get("docid") or "").lstrip("#"),
            "score": score,
            "line": r.get("line"),
            "title": str(r.get("title") or ""),
            "snippet": _clean_snippet(str(r.get("snippet") or "")),
        })
    return {"hits": hits, "outcome": "ok", "error": ""}
