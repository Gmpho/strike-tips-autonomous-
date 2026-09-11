## Why

Production showed three linked failures: (1) phantom LOST settlements before off-time due to TAB `12:00` placeholders + UTC/ SAST mismatch + winner stoplist gaps, (2) exotic board showing `#1` cloth numbers and missing distances due to TAB numbers-mode and collapsed history, and (3) Betfair off-times never reaching the settlement gate due to `marketStartTime` miss + course decoration + missing `eventDate`.

## What Changes

* **Settlement gate:** Betfair `marketStartTime` → `offTime`/`eventDate`/`distanceM` + SAST-aware `bf_off_time` stamping + 15-min grace, stoplist expansion, `void_settlement` for phantom LOSTs, `MAX_SETTLE_AGE_DAYS` guard, duplicate guards.
* **Exotic board:** `exotics_history.json` merge-by-day (event_date + track), `distanceM` threading, source chips, numeric-name guards, future-board countdown.
* **Volume sync:** throttled `Volume.reload` in API middleware + SSE + scheduler to fix 18h stale volume view.
* **Distance:** Betfair `1200m`/`6f`/`1m1f` parser + snapshot/scan/exotic/HUD wiring.

## Capabilities

### New Capabilities
- `betfair-offtime-threading`: exact Betfair startTime stamping and SAST-aware settlement gating.

### Modified Capabilities
- `settlement-accounting`: off-time gate, stoplist, void path, date-matched stamp logic.
- `atr-fetch-resilience`: volume sync and staleness handling (overlaps, but primary spec is settlement).
- `betfair-form-data`: `offTime`/`eventDate`/`distanceM` fields and cleaning.

## Impact

* `core_agent/skills/parsers/betfair_sa.py` (marketStartTime, course clean, eventDate, distance, offTime)
* `core_agent/core/adaptive_odds_monitor.py` (bf_off_time/bf_event_date/distance_m stamping, fallback match)
* `core_agent/skills/result_tracker.py` (SAST gate, stoplist, void, max-age)
* `core_agent/skills/bankroll_manager/governor.py` (void, duplicate guard, history floor)
* `core_agent/core/strike_tips.py` (exotic history merge, numeric guard, distance)
* `strike-tips-hud/src/components/ExoticsView.tsx` / `RaceCard.tsx` / `types` (countdown, distance, source chip)
* `core_agent/core/volume_sync.py` (new), `core_agent/api_pkg/__init__.py`, `core_agent/routes/monitoring.py`, `core_agent/core/scheduler.py`
* Tests: `test_settlement_chain.py` + `test_betfair_*` + `test_governor` (145 passed)
