---
title: Verify the deploy, not just the merge
tags: [lesson, coding]
created: 2025-01-15
updated: 2025-01-15
status: active
type: lesson
domain: coding
confidence: high
---
**Regel / Rule:** Ein grüner Merge ist kein grüner Deploy — prüfe, dass die Änderung wirklich in Produktion gelandet ist. / A green merge is not a green deploy — verify the change actually shipped to prod.

## Fehler / What went wrong
- Der Pull Request war gemergt, alle Checks grün — also galt die Aufgabe als erledigt. In Produktion lief aber noch die alte Version, weil die Deploy-Pipeline still fehlgeschlagen war. / The pull request was merged, all checks green — so the task was treated as done. But prod still ran the old version because the deploy pipeline had silently failed.
- Ein Nutzer meldete den "schon gefixten" Bug Stunden später erneut. / A user re-reported the "already fixed" bug hours later.

## Fix (nur Verifiziertes / verified only)
- ✓ Nach dem Merge aktiv prüfen: Deploy-Status, eine Versions-/Build-Kennung im Live-System und das tatsächliche Verhalten in Produktion. / After merge, actively check: deploy status, a version/build identifier in the live system, and the real behavior in prod.
- ✓ Einen sichtbaren Health- oder Version-Endpoint nutzen, der die ausgelieferte Revision zurückgibt. / Use a visible health or version endpoint that returns the shipped revision.

## Was NICHT funktioniert / What does NOT work
- ✗ Annehmen, dass "merged" gleich "deployed" ist — CI und CD sind getrennte Schritte und können unabhängig scheitern. / ✗ Assuming "merged" equals "deployed" — CI and CD are separate steps and can fail independently.

## Warum / Why
- Merge und Deploy sind zwei verschiedene Ereignisse. Ein grüner Merge beweist nur, dass der Code integriert wurde, nicht dass er ausgeliefert und aktiv ist. Verifikation muss am letzten beobachtbaren Punkt der Kette ansetzen — dem realen Verhalten in Produktion. / Merge and deploy are two distinct events. A green merge only proves the code was integrated, not that it shipped and is live. Verification must happen at the last observable point in the chain — real behavior in production.

## Links
- [[never-force-push-a-shared-branch]] · [[cap-llm-api-costs-with-a-hard-limit]]
