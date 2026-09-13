## 1. Settlement core

- [x] 1.1 Leg evaluator (banker-or-saver, pool requirements, fuzzy 0.55, definitive-fail only)
- [x] 1.2 Dividend-gated WON (`_extract_pool_dividend`, SA number format)
- [x] 1.3 ATR-window guard (age ≤ 1) + off-time gate on last leg
- [x] 1.4 Dedupe-at-settle + EXPIRED sweep + `cancel_pending_bet` + `expire_stale_bet` + `POST /api/betting/void`

## 2. Meeting integrity

- [x] 2.1 `_betfair_course_dates` + `_drop_meetings_not_running_today` in morning scan
- [x] 2.2 Per-track exotic building (no first-key label)
- [x] 2.3 `_play_matches_snapshot` phantom guard + snapshot reuse
- [x] 2.4 Live remediation: Vaal card re-stamped vaal/2026-09-17 and kept; phantom JP1 cancelled/refunded

## 3. Verify

- [x] 3.1 175+ tests green (16 exotic-settlement, 8 meeting-gate, governor cancel/expire)
- [x] 3.2 Modal deployed; board shows vaal/2026-09-17; void endpoint cancels with refund
