---
title: Reproduce and read the actual error before editing
tags: [lesson, coding]
created: 2025-01-15
updated: 2025-01-15
status: active
type: lesson
domain: coding
confidence: high
---
**Regel / Rule:** Reproduziere den Fehler und lies die echte Fehlermeldung, BEVOR du Code änderst. / Reproduce the failure and read the actual error message BEFORE editing code.

## Fehler / What went wrong
- Auf eine vermutete Ursache hin wurde Code geändert, ohne den Fehler je reproduziert zu haben. Die Vermutung war falsch, die Änderung machte es schlimmer und verschleierte die wahre Meldung. / Code was changed on a hunch about the cause, without ever reproducing the failure. The hunch was wrong, the change made it worse and hid the real message.
- Die eigentliche Stacktrace-Zeile nannte die Ursache klar — sie wurde nur nie gelesen. / The actual stack-trace line named the cause plainly — it was simply never read.

## Fix (nur Verifiziertes / verified only)
- ✓ Den Fehler zuerst lokal reproduzieren und die vollständige Meldung samt Stacktrace lesen. / Reproduce the failure locally first and read the full message including the stack trace.
- ✓ Datei, Zeile und Exception-Typ aus der Meldung als Startpunkt nehmen, nicht die Intuition. / Take the file, line and exception type from the message as the starting point, not intuition.
- ✓ Eine kleinste Änderung machen, dann erneut reproduzieren, um zu bestätigen, dass sie greift. / Make one smallest change, then reproduce again to confirm it actually fixes it.

## Was NICHT funktioniert / What does NOT work
- ✗ Code "nach Gefühl" anpassen, ohne den Fehler gesehen zu haben — das jagt Symptome statt Ursachen. / ✗ Tweaking code "by feel" without having seen the failure — that chases symptoms instead of causes.

## Warum / Why
- Die Fehlermeldung ist die billigste und genaueste Informationsquelle, die es gibt — sie zeigt direkt auf den Fehlerort. Ohne Reproduktion kann man eine Korrektur nicht verifizieren; man rät nur und tauscht einen Bug gegen einen anderen. Erst lesen, dann ändern, dann erneut prüfen. / The error message is the cheapest, most accurate source of information available — it points straight at the fault site. Without reproduction you cannot verify a fix; you only guess and trade one bug for another. Read first, then edit, then re-check.

## Links
- [[cap-llm-api-costs-with-a-hard-limit]] · [[verify-the-deploy-not-just-the-merge]]
