# Changelog

## 2026-08-21 — News Feed Fix + Money-Math & Stability Fixes

### News Feed Blank on Production (Root Cause Fix)

- **Root cause**: `NewsView.tsx` fetched `/api/news` but discarded the response ("DataBridge handles store update via SSE"), and its SSE handler also no-op'd — while `DataBridge` (the designated store updater) had **no `news` listener at all**. The store's `news` array was never written → permanent "No News Yet" state.
- **`data-bridge.ts`**: added `news` SSE event listener (backend stream already emitted `event: news`) + `hydrateNews()` REST fetch on startup for instant load; exposed `refreshNews()` for the Refresh button.
- **`NewsView.tsx`**: converted to a dumb render component — removed the dead fetch effect and duplicate EventSource connection (DataBridge owns all fetching per architecture); loading resolves when data lands or after an 8s safety timeout.
- **HTML summaries**: Guardian RSS embeds markup (`<ul><li>…`) — added `cleanSummary()` (DOMParser-based tag strip + entity decode) in `NewsCard`.
- **Backend**: `/api/news` (REST) and `event: news` (SSE) were always correct — polling via `swarm_researcher.poll_news()` writes `data/news_latest.json`.

### 🔴 Money-Correctness

- **Exotic double-deduction** (`governor.py`): real-mode exotic bets deducted ticket cost at placement AND again inside settlement credit (net `return − 2×stake`). Settlement now credits dividend only; peak bankroll updates on exotic wins.
- **DSI staking was inert**: every caller except one invoked `calculate_max_stake(edge)` without `track`/`race_number`, so Dream Stress Index never scaled stakes. Now wired through `place_bet`, Telegram advised-stake (daily scan + midday rescan), and the MCP `calculate_max_position` tool.
- **Paper mode now uses full Kelly×DSI sizing** against paper balance (was flat 5%) — paper results become meaningful previews of live behavior. `calculate_max_stake()` gained a `balance` override.
- **Phantom odds blocked**: auto-bet paths defaulted missing odds to an assumed 2.0, corrupting stake sizing/settlement/learning stats. New `resolve_auto_bet_odds()` helper skips bets without a real market price (>1.01).

### 🔴 Broken Features

- **"Recent results" query** (`task_router.py`): built the results list then returned "No results found" anyway (dedented return). Fixed.
- **Telegram N+1 flood**: AgentLoop streams deltas AND a final message; TelegramChannel sent every delta as its own message plus the full duplicate. Deltas are now skipped for Telegram (one clean message per reply).
- **Exotic pool leg-counts**: extraction codes (`JP1`, `BI1`, `P6`, `PA`) never matched long-name keys (`"JACKPOT 1"`, `"PICK 6"`…) so every pool fell back to 4 legs. New `resolve_pool_legs()` in `skills/exotics/builder.py`: JP→4, BI→6, P6→6, PA→7.

### 🟡 Resource / Robustness

- **Undrained `MessageBus.outbound` queue** deleted — it was written on every outbound message and consumed by nothing (unbounded memory growth).
- **Rate-limit store leak** (`api_pkg/__init__.py`): stale ip:path keys now evicted + 10k hard cap.
- **Dream mock pollution**: custom dreams for races missing from the snapshot fabricated a "Mock Runner" race and persisted it to ChromaDB/LearningEngine, polluting DSI queries. Now returns a clean no-persist placeholder.

### 🟢 Minor

- Local-only mode actually routes AUTO to local Ollama (was a no-op assignment).
- Telegram falls back to plain text when Markdown parsing fails (message no longer lost).
- FastAPI lifespan None-guards (monitor/tg_channel/bg_task) prevent NameError in shutdown.
- Dreamer reads jockey/odds/form from the favorite runner instead of nonexistent event-level fields.

### Tests

- Suite grew 16 → **30 tests**: exotic settlement regression (real + paper), Kelly balance override, paper Kelly staking, pool leg mapping, auto-bet odds resolution.

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
