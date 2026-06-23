---
description: Capture an idea (hook | video | posting | product) into ~/vault/ideas/<kind>/. Frictionless, one-liner ok.
argument-hint: "[kind?] <idea>, e.g. 'hook the headline you can't scroll past' or 'product weekly-review command'"
---

You are filing an **idea** into the user's Personal OS (`~/vault/ideas/`, rules: `~/vault/CLAUDE.md`).
Frictionless: the user tosses in a sentence, you sort it.

Steps:

1. Determine `kind`: the first word of `$ARGUMENTS` if it is hook|video|posting|product;
   otherwise guess from keywords (a headline/hook phrasing → hook; "video", scene, cut →
   video; platform/caption/thread → posting; tool/feature/business → product).
   Only ask ONE question on genuine ambiguity.
2. Duplicate check: `grep -ril "<keyword>" ~/vault/ideas/ 2>/dev/null` — hit → append there as a
   variant instead of a new file.
3. New note `~/vault/ideas/<kind>/<kebab-slug>.md` per the template `~/vault/_templates/idea.md`.
   ALWAYS store hooks verbatim, in quotes (the exact wording is the asset). `status: active`,
   `project:` if project-related, else `cross`.
4. ≥2 wikilinks (e.g. a matching knowledge note, a profile note, the project hub).
5. No git commit. Report: 1 line — kind + path.
