---
title: Always set a hard spend cap before shipping any LLM API call
tags: [lesson, coding]
created: 2025-01-15
updated: 2025-01-15
status: active
type: lesson
domain: coding
confidence: high
---
**Regel / Rule:** Setze IMMER ein hartes Ausgabenlimit, bevor du einen LLM-API-Aufruf live schaltest. / ALWAYS set a hard spend cap before shipping any LLM API call.

## Fehler / What went wrong
- Eine Retry-Schleife um einen LLM-Aufruf hatte keinen Abbruch. Über Nacht lief sie tausende Male durch und produzierte eine absurd hohe Rechnung. / A retry loop around an LLM call had no exit condition. Overnight it ran thousands of times and produced an absurd bill.
- Kein Alarm schlug an, weil niemand ein Budget am Provider hinterlegt hatte. / No alert fired because nobody had configured a budget at the provider.

## Fix (nur Verifiziertes / verified only)
- ✓ Provider-seitiges Budget-Cap aktiviert (harte Obergrenze, die Requests blockt, nicht nur warnt). / Enabled a provider-side budget cap (a hard ceiling that blocks requests, not just warns).
- ✓ Lokaler Token-Guard vor jedem Call: zähle geschätzte Tokens, brich ab, wenn ein Tages-/Job-Budget überschritten würde. / Local token guard before each call: estimate tokens, abort if a per-day / per-job budget would be exceeded.
- ✓ Retry-Schleifen mit maximaler Versuchszahl UND exponentiellem Backoff begrenzt. / Bounded retry loops with a max attempt count AND exponential backoff.

## Was NICHT funktioniert / What does NOT work
- ✗ Sich nur auf E-Mail-Warnungen vom Provider verlassen — die kommen zu spät und nachts liest sie niemand. / ✗ Relying only on provider email warnings — they arrive too late and nobody reads them at night.

## Warum / Why
- LLM-Kostenbugs sehen aus wie Logikbugs: Der Code "funktioniert", er macht nur zu oft genau das Falsche. Der Schaden ist finanziell, nicht funktional, deshalb fängt ihn kein Test ab. Ein hartes Limit verwandelt einen stillen Geldverlust in einen lauten, frühen Fehler. / LLM cost bugs look like logic bugs: the code "works", it just does the wrong thing too many times. The damage is financial, not functional, so no test catches it. A hard cap turns a silent money leak into a loud, early failure.

## Links
- [[read-the-error-message-before-changing-code]] · [[verify-the-deploy-not-just-the-merge]]
