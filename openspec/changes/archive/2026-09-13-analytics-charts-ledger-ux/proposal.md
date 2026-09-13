## Why

Analytics was hand-rolled SVG/CSS (single equity line, fake-proportioned bars, win rate collapsed to 9.9% by counting open bets) and the bankroll ledger showed the oldest 20 rows with no dates, no status, no P&L. Not a professional look for a future open-source/SaaS product.

## What Changes

* ApexCharts suite (treeshaken core + 7 types, lazy chunk, native wrapper — no react-apexcharts React-19 risk): equity curve with max-drawdown annotation, daily P&L bars + cumulative line, diverging ROI-by-track bars, odds-bracket columns, win/loss donut, P&L histogram, track×odds ROI heatmap.
* Win rate + avg stake computed over settled bets only (matches donut).
* Ledger: newest-first, Today/Yesterday day groups, WON/LOST/OPEN/VOID/EXPIRED pills, per-row P&L, SAST timestamps, All/Wins/Losses/Open filters, paginated.
* Backend: `status` passthrough on /history + /open (additive, keyed paths unchanged).
* Fixes folded in: theme-toggle stopPropagation (was navigating to bankroll), fast poll 15s→10s, telemetry disk mirror (cross-container SSE), SW v2.6.0 + v1.1.0.

## Capabilities

### New Capabilities
- `analytics-charts`: ApexCharts suite, lazy chunk, settled-only KPIs.
- `ledger-ux`: timestamped, filterable, day-grouped executions ledger.

### Modified Capabilities
- (none — backend status field is additive)

## Impact

* `strike-tips-hud/src/components/analytics/*`, `src/lib/analytics.ts`, `src/components/sidebar/{AnalyticsView,BankrollView}.tsx`, `src/engine/data-bridge.ts`, `src/components/ThemeToggle.tsx`, `public/sw.js`
* `core_agent/core/telemetry.py` (JSONL mirror), `core_agent/models/betting.py` + `routes/betting.py` (status field)
* Deployed: Modal + Pages prod verified (7 charts render, ledger grouped, toggle stays put).
