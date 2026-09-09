## 1. Settlement tracker (`core_agent/skills/result_tracker.py`)

- [x] 1.1 Add `atr_date_label()` (ISO→today/yesterday, fail-open) and use it for the ATR lookup; verify the ATR layer receives `today`, never a raw ISO string
- [x] 1.2 Add `_extract_race_winner()` + different-winner LOST settlement path (0.55 fuzzy cutoff); verify win and loss cases
- [x] 1.3 Add `_is_exotic_bet()` skip (EXOTIC confidence or `:` in horse); verify no lookup/settle runs for pool tickets
- [x] 1.4 Honor the `settled` flag from `brain.strike.settle_bet` status dicts with governor fallback; verify a `settled: false` dict records exactly one fallback settle, never a phantom
- [x] 1.5 Add `MAX_SETTLE_AGE_DAYS = 3` + `_bet_age_days()` + per-bet deferral with review log; verify 9-day-old defers, 3-day boundary processes, garbage dates fail open, override param works
- [x] 1.6 Wrap the `strike_brain` import in try/except so settlement degrades to the injected governor instead of crashing

## 2. Governor (`core_agent/skills/bankroll_manager/governor.py`)

- [x] 2.1 Add real `get_bankroll_history()` per active ledger (backward-from-live, floored at 0); verify empty→current, win/loss reconciliation, refill-drift flooring
- [x] 2.2 Add `report_date` param to `generate_daily_report()` with renamed date-aware sections; verify date filtering
- [x] 2.3 Add aged-backlog review section (cap 20 + overflow); verify old pending appears, young pending does not
- [x] 2.4 Filter `get_open_exposure()` to active (non-stale) bets with `include_stale` opt-in; verify wall lifted with R2500 stale backlog and unparseable dates fail open

## 3. Service + scheduler wiring

- [x] 3.1 Add `StrikeTips.generate_report(report_date)` passthrough; verify
- [x] 3.2 Add `morning_report` 07:00 SAST cron + Telegram recap sender sharing `_send_report_async`; verify both job registrations and trigger times
- [x] 3.3 Route account-summary display through `get_open_exposure()` (`core_agent/routes/betting.py`); verify exposure dropped (R4247 → R510 prod)

## 4. Verification

- [x] 4.1 New `core_agent/tests/test_settlement_chain.py` (20 tests) green
- [x] 4.2 Full suite green: 131 passed host, 129 passed Docker (incl. scheduler job test)
- [x] 4.3 Prod probes: account-summary, bankroll-history (no more -43 start, no more 500), stats settled-only math
- [x] 4.4 Fix fallout found by tests: `test_governor.py` header rename, host env repair (dotenv/prometheus/opentelemetry/polars/chromadb/pytest-asyncio), DSI chromadb-stub ordering fix in `test_betfair_enriched.py`
