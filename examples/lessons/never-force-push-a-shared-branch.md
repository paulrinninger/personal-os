---
title: Never force-push a branch others may have pulled
tags: [lesson, coding]
created: 2025-01-15
updated: 2025-01-15
status: active
type: lesson
domain: coding
confidence: high
---
**Regel / Rule:** Mache NIEMALS `git push --force` auf einen Branch, den andere schon gezogen haben könnten. / NEVER `git push --force` a branch that others may already have pulled.

## Fehler / What went wrong
- Ein `git push --force` auf einen geteilten Branch hat fremde Commits überschrieben. Die Arbeit eines anderen war aus der Remote-History verschwunden. / A `git push --force` on a shared branch overwrote someone else's commits. Their work vanished from the remote history.
- Beim nächsten `git pull` bekamen alle anderen Merge-Konflikte und divergierende Historien. / On the next `git pull` everyone else got merge conflicts and diverging histories.

## Fix (nur Verifiziertes / verified only)
- ✓ Auf eigenen, nicht geteilten Branches `--force-with-lease` statt `--force` benutzen — es bricht ab, wenn der Remote sich seit deinem letzten Fetch geändert hat. / On your own, unshared branches use `--force-with-lease` instead of `--force` — it aborts if the remote changed since your last fetch.
- ✓ Geteilte Branches (z. B. `main`) gar nicht force-pushen; stattdessen einen neuen Commit oder `git revert` nutzen. / Do not force-push shared branches (e.g. `main`) at all; use a new commit or `git revert` instead.
- ✓ Verlorene Commits über `git reflog` wiederfinden und neu pushen. / Recover lost commits via `git reflog` and re-push them.

## Was NICHT funktioniert / What does NOT work
- ✗ "Schnell `--force` und danach Bescheid sagen" — die History ist dann schon kaputt und das Aufräumen kostet alle Zeit. / ✗ "Quick `--force`, tell people after" — the history is already broken and cleanup costs everyone time.

## Warum / Why
- `--force` schreibt die Remote-History blind um und nimmt keine Rücksicht auf das, was andere lokal haben. `--force-with-lease` prüft erst, ob der Remote noch dem Stand entspricht, den du erwartest, und ist deshalb auf eigenen Branches sicher. Geteilte History ist gemeinsames Eigentum — sie umzuschreiben ist destruktiv per Definition. / `--force` blindly rewrites remote history and ignores what others hold locally. `--force-with-lease` first checks the remote still matches the state you expect, making it safe on your own branches. Shared history is common property — rewriting it is destructive by definition.

## Links
- [[verify-the-deploy-not-just-the-merge]] · [[read-the-error-message-before-changing-code]]
