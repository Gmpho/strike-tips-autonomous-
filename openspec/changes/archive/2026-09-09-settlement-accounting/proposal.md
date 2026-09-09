## Why

Bets stayed PENDING forever: the bankroll never moved, the daily report showed
only pending bets with zero wins/losses, and every downstream analytic (win
rate, ROI, exposure, tracks, brackets, bankroll history, learning insights)
read empty. Three compounding defects caused it: (1) the settlement tracker
passed raw ISO bet dates (`2026-09-04`) to the ATR lookup, which builds
`/results/<date>` URLs that 404 — killing the primary settlement source for
every bet; (2) only wins were ever recorded, losses silently dropped; (3)
exotic pool tickets flowed through single-winner matching that could never
resolve them, burning lookup budget and staying pending forever.

## What Changes

- ATR date handling: ISO bet dates map to `today`/`yesterday` labels before
  the ATR lookup (`atr_date_label()`), with safe fallbacks.
- Win AND loss settlement: a confirmed different winner settles the bet LOST
  via `_extract_race_winner()` + fuzzy match (0.55 cutoff).
- Exotic tickets are explicitly skipped by the single-winner settler (they
  need pool dividends, resolved separately).
- Phantom-settle guard: the tracker's success flag honors the `settled` field
  of the `settle_bet` status dict instead of assuming any dict means success.
- Max-age guard (`MAX_SETTLE_AGE_DAYS = 3`): bets older than 3 days are
  deferred for manual review instead of being settled against the wrong race.
- Dated reports: `generate_daily_report(report_date)` + 07:00 SAST morning
  recap of yesterday alongside the 20:00 end-of-day report; aged-backlog
  review section surfaces deferred bets.
- Bankroll history: real `get_bankroll_history()` on the governor (the route
  called a method that did not exist → HTTP 500), reconstructed backward from
  the live balance per active ledger, floored at zero.
- Exposure accounting: stale (>3d) pending bets excluded from
  `get_open_exposure()`/`can_bet_today()` so a dead backlog no longer walls
  the governor against all new bets.

## Capabilities

### New Capabilities
- `settlement-accounting`: auto-settlement, dated reporting, bankroll history,
  and exposure rules described above.

### Modified Capabilities
(none — no prior spec covered settlement.)

## Impact

- `core_agent/skills/result_tracker.py` (ATR labels, exotic skip, age guard,
  settled-flag honor, brain-import tolerance)
- `core_agent/skills/bankroll_manager/governor.py` (`get_bankroll_history()`,
  dated `generate_daily_report()`, aged section, exposure filter)
- `core_agent/core/strike_tips.py` (`generate_report(report_date)` passthrough)
- `core_agent/core/scheduler.py` (`morning_report` 07:00 SAST job)
- `core_agent/routes/betting.py` (uses `get_open_exposure()` for display)
- `core_agent/tests/test_settlement_chain.py` (20 tests), `test_governor.py`
  (header rename)
- HUD Bankroll/Analytics views consume the fixed endpoints unchanged.
