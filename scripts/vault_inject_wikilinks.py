#!/usr/bin/env python3
"""vault_inject_wikilinks.py — inject [[wikilink]] edges into the vault graphify graph. $0, no LLM.

graphify's lexical markdown extractor only emits File- and Heading-nodes with `contains`
edges — every note is an isolated star. This script parses Obsidian wikilinks from the
vault notes and adds `references` edges between the corresponding File-nodes, so
`graphify query/path` can traverse the knowledge network.

Idempotent: removes its own previously injected edges (marker `_injected`) before adding.
Must re-run after every `graphify update <vault>` (full rebuild drops injected edges).

Usage: python3 vault_inject_wikilinks.py [VAULT_DIR]
       (default: $PERSONAL_OS_VAULT or ~/vault)
"""
import json, os, re, sys

default_vault = os.environ.get("PERSONAL_OS_VAULT", "~/vault")
vault = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else default_vault)
gpath = os.path.join(vault, "graphify-out", "graph.json")
if not os.path.isfile(gpath):
    sys.exit(f"no graph at {gpath} — run `graphify update {vault}` first")

MARKER = "vault-wikilinks"
SKIP_DIRS = {"graphify-out", ".obsidian", ".trash", ".git", "node_modules"}
WIKILINK = re.compile(r"\[\[([^\]\|#\n]+)")

g = json.load(open(gpath))
nodes = g["nodes"]
links = g.get("links", [])

# map: note name (basename, lower, no .md) -> file-node id
name_to_id = {}
for n in nodes:
    sf = n.get("source_file") or ""
    if not sf.endswith(".md"):
        continue
    base = os.path.basename(sf)
    if str(n.get("label", "")) == base:  # the File node (headings carry heading text as label)
        name_to_id.setdefault(base[:-3].lower(), n["id"])

before = len(links)
links = [e for e in links if e.get("_injected") != MARKER]
removed = before - len(links)

added, unresolved, seen = 0, 0, set()
for root, dirs, files in os.walk(vault):
    dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
    for f in files:
        if not f.endswith(".md"):
            continue
        rel = os.path.relpath(os.path.join(root, f), vault)
        src_id = name_to_id.get(f[:-3].lower())
        if not src_id:
            continue
        try:
            text = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in WIKILINK.finditer(text):
            target = os.path.basename(m.group(1).strip()).lower()
            tgt_id = name_to_id.get(target)
            if not tgt_id:
                unresolved += 1
                continue
            if tgt_id == src_id or (src_id, tgt_id) in seen:
                continue
            seen.add((src_id, tgt_id))
            links.append({
                "relation": "references", "confidence": "EXTRACTED", "confidence_score": 1.0,
                "source_file": rel, "source_location": "wikilink", "weight": 1.0,
                "source": src_id, "target": tgt_id, "_injected": MARKER,
            })
            added += 1

g["links"] = links
# Atomic write (tmp + os.replace): a crash mid-dump must never tear graph.json apart —
# a torn graph silently breaks every `graphify query` until the next full rebuild.
tmp = gpath + ".tmp"
with open(tmp, "w") as f:
    json.dump(g, f, ensure_ascii=False)
os.replace(tmp, gpath)
print(f"OK: {added} wikilink edges injected ({removed} stale removed, "
      f"{unresolved} unresolved targets, {len(name_to_id)} note nodes). $0.")
