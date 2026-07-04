---
description: Show or review pending cold-outreach text drafts rendered by the nightly "producer" pass. 'review' creates REAL Gmail drafts after a yes — never automatically, never sent.
argument-hint: "[optional: 'review' = go through pending drafts]"
---

You're working with the optional `producer` pass of the nightly dreaming job (`dream_run.sh` /
`dream.py`, registered via the installer's `--schedule-dream` flag). It renders pure template text
from `~/.personal-os/producer-queue.jsonl` — a queue **you fill in yourself** with real lead data,
required fields `id` (identifies the entry so it can be cleared from the queue once rendered) and
`observation`/`pain_point` (a model can't invent a real prospect's pain point, so entries missing
any of these are skipped, never silently generated) — against
`~/.personal-os/producer-templates.json` into `~/vault/_inbox/producer-drafts/`. **No LLM call is
involved in rendering.** Since `dream.py` runs as a standalone cron script with no MCP access, it
can never send anything or create a real Gmail draft — that only ever happens here, in this
session, after you say yes.

**Display mode** (default, or no argument):

1. `ls -t ~/vault/_inbox/producer-drafts/*.md 2>/dev/null` — show count + lead/playbook for each
   pending draft (`status: draft` in frontmatter). None found → "Nothing to review." Stop.

**`review` mode** (`$ARGUMENTS` == `review`):

1. Read all `_inbox/producer-drafts/*.md` with `status: draft`, newest first.
2. Show each compactly: lead company, playbook, a short preview of the rendered text. Bundle a few
   per question (up to 4), options: yes (create draft) / no (discard) / edit (you edit the file
   yourself, then ask again).
3. **On yes:** call the Gmail draft-creation tool with the rendered text (ask for the recipient
   address if it isn't already in the lead data). **Never call send.** Immediately follow up with
   an unmissable confirmation: "DRAFT ONLY — NOT SENT, sitting in Gmail drafts for `<lead_company>`."
   (This mirrors the project's own lesson about never sending email automatically — Gmail renders
   drafts inline, easy to mistake for sent at a glance, so explicit chat-text confirmation is not
   optional.)
4. **On no:** set `status: parked` in the draft's frontmatter. Never delete it.
5. Append one line per decision to `~/.personal-os/producer-feedback.jsonl`:
   `{"id":"<draft-id>","pass":"producer","verdict":"accepted|rejected","ts":"<ISO>"}` — a separate
   channel from `~/.personal-os/dream-feedback.jsonl` (different acceptance context; mixing them
   would skew the other dreaming passes' adaptive thresholds).
6. Report: N drafts created (with subject/recipient), M discarded, how many queue entries are still
   incomplete (per the latest `producer.json` pass state).

Never: create or send a draft without an explicit yes, invent lead data or pain points, make up
template variables, delete a draft instead of parking it.
