# Proposal: Alert Digest v2

Telegram odds alerts read as naked tips (no race, no time, no journey, no
action). Users confuse movers with selections. Digest v2 attaches race
context, an open→latest odds journey, form enrichment, and an explicit
action frame — movers only, short lines, one featured wobble card.

## Scope
- `core_agent/core/alert_engine.py`: race context + journey tracking on
  every alert message (race number, off-time, minutes-to-off, open odds).
- New journey store (day-scoped volume JSON): first-seen odds per
  (day, course, race, horse).
- `core_agent/core/alert_digester.py`: collapse repeats per horse (trail
  line), STEAMER/DRIFTER + value/watch-only framing, movers header/footer,
  featured biggest-mover card.
- Enrichment passthrough (trainer, claim, form, days-since-run, rating,
  edge) with graceful fallback; pedigree/owner stay on the racecard.
- Tests: journey store, collapse, render, single-universe numbers.
