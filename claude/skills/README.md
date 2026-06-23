# Skills

Personal OS uses two third-party CLIs for retrieval. Both are **required but not vendored** —
you install them yourself (see `docs/SETUP.md`), and each keeps its own license.

## qmd (semantic / meaning search)
A small bootstrap skill ships here in `qmd/SKILL.md`. It just calls `qmd skill show`, so the
instructions stay version-matched to whatever `qmd` you have installed. qmd is MIT, by Tobi Lutke —
https://github.com/tobi/qmd

## graphify (structural / knowledge-graph queries)
graphify installs and manages its **own** Claude Code skill when you set it up — there is nothing to
vendor here. After `uv tool install graphifyy`, run `graphify --help` (and see the project docs) to
wire up its skill. graphify is MIT, by Safi Shamsi — https://github.com/safishamsi/graphify

If you already have a `graphify` skill in `~/.claude/skills/`, the installer leaves it untouched.
