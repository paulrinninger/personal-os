# Personal OS — ~/vault (Obsidian, local, $0)

Your cross-project memory lives in `~/vault/`. Entry point: `~/vault/HOME.md`, rules: `~/vault/CLAUDE.md`.
In EVERY project:
- Before risky/novel work: `qmd query "<keyword>"` (semantic — finds paraphrased/cross-lingual lessons
  that grep/graphify miss) or `grep -ril "<keyword>" ~/vault/lessons/` — read the hits.
- Your standards (design, style, expectations): `~/vault/profile/` — act on them.
- Capture: `/save` (session log + lessons/ideas harvest), `/lesson`, `/idea`; overview `/os`.
- If you (the user) report a bug that came from EARLIER Claude work (thought correct yesterday, broken
  today): right after the fix, IMMEDIATELY write a lesson (like /lesson, with the why + a dedup check) —
  don't wait for /save. That's the system's most important learning moment.
- Knowledge/lesson questions by MEANING → FIRST `qmd query "<question>"` (hybrid BM25+vector+RRF+reranker,
  multilingual; returns cited passages + score, then `qmd get <docid>` for full text). Pure modes without
  an LLM: `qmd search` (BM25), `qmd vsearch` (vector).
- Questions about STRUCTURE/connections/cross-project paths → `graphify query "<question>"
  --graph ~/vault/graphify-out/graph.json` (or `--graph ~/.graphify/global-graph.json`).
  Rule of thumb: qmd = meaning/passages, graphify = structure/links. Both complementary, both $0 & local.
- Never delete vault notes without asking. No API/LLM pipelines into the vault ($0 policy) — qmd is
  compliant: local inference (GGUF) ONLY at query time, NO API key, index in `~/.cache/qmd/` outside the
  vault; it never writes into vault notes.
