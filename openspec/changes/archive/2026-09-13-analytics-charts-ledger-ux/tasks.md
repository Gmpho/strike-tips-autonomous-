## 1. Charts

- [x] 1.1 `lib/analytics.ts` transforms (daily P&L, drawdown, streaks, brackets, heatmap, histogram)
- [x] 1.2 Native ApexChart wrapper + dark theme + 7 chart components (lazy chunk)
- [x] 1.3 AnalyticsView rewire (KPIs kept, settled-only math); fix empty equity ("Start" anchor) + heatmap shades + KPI denominators found in visual review

## 2. Ledger

- [x] 2.1 Backend `status` on /history + /open (additive)
- [x] 2.2 BankrollView ledger rewrite (newest-first, day groups, pills, P&L, filters, paging)

## 3. Folded fixes

- [x] 3.1 Theme toggle stopPropagation (was navigating to bankroll via Capital pill)
- [x] 3.2 Fast poll 15s→10s (~19.5k/day vs 100k quota)
- [x] 3.3 Telemetry JSONL mirror + test isolation (7 tests green)
- [x] 3.4 SW v2.6.0 + v1.1.0, Modal + Pages deployed and browser-verified
