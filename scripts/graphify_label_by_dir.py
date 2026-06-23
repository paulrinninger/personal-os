#!/usr/bin/env python3
"""graphify_label_by_dir.py — deterministic, $0 community labels for a graphify code graph.

graphify's LLM labeling (--backend ollama/gemini/...) is flaky on large graphs and costs
tokens/time. For a CODE graph, communities map cleanly onto directories, so we derive an
honest name from each community's dominant directory + its top-degree representative symbol.
No LLM, no API, no network — pure structure. Writes graphify-out/.graphify_labels.json and
prints the largest modules as a map.

Usage: python3 graphify_label_by_dir.py [REPO_DIR] [--top N]
"""
import json, collections, os, sys

repo = next((a for a in sys.argv[1:] if not a.startswith("--")), ".")
top = 25
if "--top" in sys.argv:
    try: top = int(sys.argv[sys.argv.index("--top") + 1])
    except Exception: pass

gpath = os.path.join(repo, "graphify-out", "graph.json")
g = json.load(open(gpath))
nodes, links = g["nodes"], g.get("links", g.get("edges", []))
deg = collections.Counter()
for e in links:
    deg[e["source"]] += 1; deg[e["target"]] += 1
by_comm = collections.defaultdict(list)
for n in nodes:
    by_comm[n.get("community")].append(n)

TRIVIAL = {"string","int","bool","double","float","view","optional","void","any","list","map",
 "array","set","dictionary","char","long","object","unit","self","result","error","data",
 "identifiable","hashable","codable","decodable","encodable","sendable","equatable","caseiterable",
 "modifier","color","text","image","true","false","nil","none","null","provider"}
# Generic package-path noise to drop from module names (extend for your own monorepo layout).
_STRIP = {"src", "main", "kotlin", "java", "com", "lib", "app", "internal", "pkg"}

def short_dir(path):
    d = os.path.dirname(path)
    if not d: return "(root)"
    parts = [p for p in d.split("/") if p not in _STRIP]
    return "/".join(parts[-2:]) if len(parts) >= 2 else ("/".join(parts) or d)

def rep_symbol(members):
    for n in sorted(members, key=lambda n: -deg.get(n["id"], 0)):
        lbl = str(n.get("label", "")).strip()
        if lbl.lower().rstrip("()") not in TRIVIAL and n.get("source_file"):
            return lbl
    return members[0].get("label", "?") if members else "?"

labels, rows = {}, []
for cid, members in by_comm.items():
    if cid is None: continue
    dirs = collections.Counter(short_dir(n["source_file"]) for n in members if n.get("source_file"))
    dom = dirs.most_common(1)[0][0] if dirs else "(no-source)"
    rep = rep_symbol(members)
    labels[str(cid)] = f"{dom} · {rep}" if dom != "(no-source)" else f"{rep} (types)"
    rows.append((len(members), cid, dom, rep))

json.dump(labels, open(os.path.join(repo, "graphify-out", ".graphify_labels.json"), "w"),
          indent=0, ensure_ascii=False)
print(f"OK: {len(labels)} communities labeled ($0). Top {top} modules:")
print(f"{'size':>5}  {'#':>4}  {'module':<40}  top-symbol")
print("-" * 80)
for size, cid, dom, rep in sorted(rows, reverse=True)[:top]:
    print(f"{size:>5}  {cid:>4}  {dom[:40]:<40}  {rep[:26]}")
