# Changelog

## 2026-07-09 — Real-Time Dashboard & Auto-Betting

### Data Freshness (Dashboard No Longer Stale)

- **Monitor sleep**: 45s → **15s** when races are active (`adaptive_odds_monitor.py`)
- **ATR data**: Fetched **every cycle** (was every 3rd cycle) — market movers, predictor, results refresh every 15s
- **ATR results**: Fetches **today** in addition to yesterday (merged into one snapshot)
- **Frontend fast poll**: 15s → **5s** (health, bankroll, open bets)
- **Frontend slow poll**: 60s → **15s** (history, stats, logs, reports)
- **Max backoffs**: Halved for faster recovery after transient failures

### SSE Push (Instant Updates)

- **New endpoint**: `GET /api/monitoring/stream` — Server-Sent Events
- Pushes `snapshot`, `market-movers`, `predictor`, `results` events the moment data changes (polled internally every 2s)
- Frontend `DataBridge` subscribes via `EventSource` — snapshot + ATR data no longer polled
- Health/bankroll/bets still polled (5s) since they change independently
- SSE added to `SAFE_PATHS` in `security.py` (EventSource can't send custom headers)
- Fallback to polling if SSE disconnects (exponential backoff, max 30s reconnect)

### Off-Time Race Auto-Close (UK/Ireland Fix)

- **New function**: `_close_overdue_races()` in `adaptive_odds_monitor.py`
- Closes races 5min past their scheduled off-time, even if Betway never sets `isFinished`
- Applied after Betway's own filter — catches UK/Ireland/Japan/Australia tracks
- Logged as `"Race auto-closed by off-time"` for observability

### PDF Odds Enrichment (Fix 5.0 Placeholder Odds)

- **Modified**: `_enrich_runners_from_pdf()` in `strike_tips.py`
- When a runner has placeholder odds (5.0 = SP) and Computaform PDF has `forecast_odds_decimal`, the real forecast odds now **overwrite** `runner.odds_decimal`
- Previously forecast odds were only appended to `form` string (annotations only)
- Now TAB-fallback tracks (Fairview, Durbanville, Greyville, etc.) get real prices from the Computaform PDF

### Auto-Betting Enabled

- **settings.json**: `auto_bet_enabled` → `true`, threshold lowered from 8% to **5.5%**
- **Guard added**: Races where all runners have 5.0 placeholder odds are skipped (phantom value bets blocked)
- **Edge key fix**: `edge_percentage` added to fallback chain (was missing, causing some value bets to be silently dropped)
- **Paper mode**: Enabled (`paper_mode: true`) — bets recorded but not placed with real money

### Files Changed

| File | Change |
|------|--------|
| `core_agent/core/adaptive_odds_monitor.py` | Sleep 45→15s, ATR every cycle, today results, off-time auto-close |
| `core_agent/routes/monitoring.py` | New SSE endpoint `/api/monitoring/stream` |
| `core_agent/core/security.py` | SSE endpoint added to SAFE_PATHS |
| `core_agent/core/strike_tips.py` | PDF odds override, placeholder guard, edge_percentage fix |
| `data/settings.json` | auto_bet_enabled=true, min_edge=5.5, paper_mode=true |
| `strike-tips-hud/src/engine/data-bridge.ts` | SSE subscription, fast 5s, slow 15s, removed ATR polling |
