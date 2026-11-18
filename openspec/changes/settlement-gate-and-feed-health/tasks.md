# Tasks: Settlement Gate Ordering & Feed Health

## 1. Gate before lookup (`result_tracker.py`)

- [x] 1.1 Move the last-leg off-time gate above `_exotic_leg_races()` in `_settle_exotic_ticket`; keep `OFF_TIME_GRACE_MINUTES` and the `_diag` args identical
- [x] 1.2 Unknown off-time still falls through to evidence (no new early return)
- [x] 1.3 Regression test asserts the lookup is never awaited for a future final leg and the reason is `before_off_time`

## 2. Feed-health banner (`strike-tips-hud`)

- [x] 2.1 Carry `feedOk` / `feedStale` / `feedError` / `feedStaleSince` from the snapshot into `hudStore`
- [x] 2.2 `FeedStaleBanner` renders only when `fetch_ok:false` or `stale:true`; non-dismissable, says prices are out of date
- [x] 2.3 Mount above the routed view; cleared automatically by the first live cycle

## 3. ATR breaker logs the trip once (`attheraces_api.py`)

- [x] 3.1 `_record_failure` WARNINGs only on the not-open → open transition, else INFO "still open (n)"
- [x] 3.2 Cooldown is still never extended by a half-open probe
- [x] 3.3 `test_atr_circuit_breaker.py` green + new test for the log transition

## 4. Identical exotic re-record (`governor.py`)

- [x] 4.1 `record_exotic_bet` returns the existing PENDING ticket when the replacement's selections are identical
- [x] 4.2 Genuinely different selections still supersede; settled tickets still untouchable
- [x] 4.3 Regression test: one PENDING row, no VOID pair

## 5. Verification

- [x] 5.1 Full suite in Docker: `pytest core_agent/tests/ -q`
- [x] 5.2 `npm run build` for the HUD
- [x] 5.3 Repair 4 date-bound tests in `test_settlement_proof_gaps.py` (hardcoded 2026-11-14 fell outside the ATR `delta <= 1` window)
