# Tasks: exotic-settlement-observability

## 1. Diagnostics module
- [x] 1.1 `settlement_diagnostics.py`: `record_pending`, `recent`, `latest_by_bet`, 1MB rotation
- [x] 1.2 Closed reason set (age_expired, unparseable, no_results, before_off_time, unknown_legs, no_dividend, settle_failed)

## 2. Instrumentation (result_tracker.py — approved by user)
- [x] 2.1 age > EXOTIC_MAX_AGE_DAYS → `age_expired`
- [x] 2.2 missing combinations → `unparseable`
- [x] 2.3 lookup error / no races → `no_results`
- [x] 2.4 before final-leg off + grace → `before_off_time`
- [x] 2.5 any indeterminate leg → `unknown_legs`
- [x] 2.6 won ticket without dividend → `no_dividend` (keeps existing healing event)
- [x] 2.7 governor refused write → `settle_failed`

## 3. Tests
- [x] 3.1 `tests/test_settlement_diagnostics.py` — 7 tests (incl. read-only volume safety)
- [x] 3.2 Exotic suites re-run green (68 passed; settlement chain 50 passed / 2 skipped)

## 4. Follow-ups (after two weeks of data)
- [ ] 4.1 Tally reasons per pool from `settlement_diagnostics.jsonl`
- [ ] 4.2 If `no_dividend` dominates → REA/HAR hunt for the tote dividend feed
- [ ] 4.3 Optionally surface `latest_by_bet()` in the HUD Live Ops panel
