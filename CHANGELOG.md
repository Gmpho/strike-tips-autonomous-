# Changelog

## 2026-08-27 — Backend cleanup: remove Cloudflare quick-tunnel, Modal stays primary

### 🔧 Routing simplified (Modal-only by default)
- Removed the Cloudflare **quick-tunnel** (`trycloudflare`/`cloudflared`) from the active code path — no tunnel in `middleware.ts`, `data-bridge.ts`, or backend CORS.
- **Modal remains the primary backend** (`serve-api`), first in priority and wins whenever healthy.
- **Cloudflare Worker MCP kept** — the fixed read/MCP endpoint set still routes to the always-on Worker, separate from the primary backend.
- Fallback is now **strictly opt-in**: set `BACKEND_FALLBACK_ORIGIN` / `VITE_SSE_FALLBACK_ORIGIN` in Vercel env (e.g. a Cloud Run URL). Nothing hard-coded.
- Backend CORS: removed the `*.trycloudflare.com` `allow_origin_regex` from `core_agent/api_pkg/__init__.py`.
- Docs rewritten with placeholders (no hardcoded URLs): `docs/FAILOVER_BRIDGE.md` + README backend section.

## 2026-08-23 — Modal Credit-Gap Failover (Cloud Run attempt → Cloudflare Tunnel bridge)

### 🚨 Situation
Modal credits exhausted until Sep 1 — production API dark. Built a failover bridge so the HUD keeps working off the local Docker stack.

### 🔌 HUD Automatic Failover
- **`middleware.ts` rewritten**: proxies `/api/*`+`/v1/*` with **real health-probe validation** (`GET /api/system/health`, 3s timeout) before trusting an origin — a suspended Modal answers `404` fast, which a naive check mistakes for healthy (bug caught pre-deploy). Healthy origin cached 60s; falls back to `BACKEND_FALLBACK_ORIGIN`.
- **`data-bridge.ts`**: SSE origins probed in priority order — dev same-origin (Vite proxy → local Docker) first, then Modal, then `VITE_SSE_FALLBACK_ORIGIN`; dark origins negative-cached 60s so reconnects don't stall.
- **Dev SSE fix**: `/predictor`, `/market-movers`, `/results` were blank in dev because SSE hardcoded to dark Modal while the dashboard showed stale localStorage. Dev now routes SSE through the Vite proxy to the local backend — verified live: 44 races, 306 movers, 42 predictions, 1,050 result races.
- Vercel env vars added: `BACKEND_FALLBACK_ORIGIN`, `VITE_SSE_FALLBACK_ORIGIN`. Production verified serving live UK/IRE card through the bridge.

### 🥅 Cloudflare Tunnel bridge
- Local Docker (`strike-bot-new`) exposed via `cloudflared` quick tunnel under a supervisor loop (`/tmp/opencode/tunnel-supervisor.sh`).
- Backend CORS: added `allow_origin_regex` for rotating `*.trycloudflare.com` hosts (`api_pkg/__init__.py`).
- Known limitation: quick-tunnel URLs rotate on restart → named tunnel (needs a CF domain) or Cloud Run are the durable options.

### ☁️ Cloud Run attempt (blocked, fully prepared)
- gcloud CLI installed via apt (snap version has broken OAuth — `redirect_uri` 400s).
- `deploy-cloud-run.sh`: one-command deploy (Cloud Build from repo Dockerfile, env from `.env`, SSE-compatible timeouts, `MIN_INSTANCES` toggle for background loops).
- Blocked on Google billing (`OR_BACR2_44` — closed billing profile, new-profile creation rejected). Resume checklist in `docs/FAILOVER_BRIDGE.md`.

### 💾 Data-divergence finding (important)
- Modal Volume `strike-tips-data` + ChromaDB Cloud **persist through the credit gap** — no production data lost. The fallback serves local Docker's own `data/` copy, so analytics/history look different until Sep 1. Bets placed during the gap land in the local copy only — reconcile into the Modal volume on return (checklist in docs).

### 📚 Docs
- New `docs/FAILOVER_BRIDGE.md` — architecture, Cloud Run resume checklist, data-divergence table, Sep 1 return checklist.

## 2026-08-22 — Live Ops Telemetry + RaceCard Table UX + News-Linking Fix

### 📡 Live Ops — Engine Telemetry Stream (new sidebar tab)

- **`core_agent/core/telemetry.py` (new)**: in-memory ring buffer (100 events, newest-first) + best-effort Redis fanout on `agent:telemetry`. `emit(engine, message, badge)` never raises; works in sync or async contexts. Events from four engines: `swarm` / `news` / `dream` / `governor`.
- **Emit points wired**: Swarm form backfill (runners tracked + Groq calls used), news polls (+ per-cycle link counts), Dream heartbeat ticks (track/race/scenario/shift), Governor DSI adjustments ("⚖️ DSI 42% → sizing ×0.75").
- **Transport**: SSE stream gained `event: telemetry` (same hash/count-check pattern as the other events) — one connection for everything; plus REST `GET /api/telemetry` for initial hydration. Both in `SAFE_PATHS`.
- **HUD — dedicated "Live Ops" tab** (`TelemetryView.tsx`, 📡 next to News): four tidy engine cards (Swarm Researcher / News RAG / Dreaming Engine / Governor) each with Active/Idle badge, relative timestamp and last message — plus a live Activity Stream below. The Agent Pipeline widget stays untouched (an earlier draft injected badges there; reverted after review).

### 🖥️ RaceCard Expanded-Table UX

- **Collapsible insight banners**: Timeform/Swarm commentary moved out of the horse cell into a full-width sub-row banner (`colSpan`) toggled by a chevron on the horse name — primary rows now keep uniform height, no more narrow-strip text squeeze on mobile.
- **Sortable headers**: click-to-sort on Horse / Age / Draw / ★ / Form / Odds with asc→desc→off cycling; default stays snapshot order.
- **Edge column**: new column before Odds shows model value `+X.X%` (emerald, tooltip = model win probability) where daily-scan value-bet data exists, em-dash otherwise.
- **Per-row ⚡ execution**: lightning button on every row opens AI Chat prefilled with that race *and focused on that specific runner* (`FOCUS RUNNER:` prompt section + session title suffix). Same safe review-in-chat flow as the card-level Execute button.

### 🔗 Governor DSI surfaced to HUD

- `calculate_max_stake` now persists last-computed DSI/scale per track:race to `data/dsi_cache.json` (capped 200 entries); snapshot enrichment stamps `event.dsi` so RaceCards show a stress chip — 🟢 <20% / 🟠 20–50% / 🔴 >50%.

### 🐛 News-linking statefulness bug (caught by Docker testing)

- `_link_news_to_insights()` read/wrote a global seen-ids file, making it stateful across runs — a first run persisted ids that silently blocked all future links (and broke tests). Refactored to a **pure function** with optional `seen_path`; `poll_news()` passes the daily file, tests stay stateless. Added persistence regression test.

### Tests

- Suite grew 30 → **44**: telemetry ring buffer/badges/cap/latest-per-engine (7) + news-linking matching, course fallbacks, short-name guard, dedupe, seen-path persistence (7). All green locally and inside Docker.

## 2026-08-21 — Swarm Researcher (All-Region Form Insights) + HUD Insight Surfaces

### 🐝 Swarm Researcher (`core_agent/skills/swarm_researcher.py` — new)

- **Problem**: Betway only publishes Timeform prose (`timeForm`) + star ratings for UK/Ireland — USA, Japan, South Africa, Australia, NZ, Hong Kong runners arrived with empty commentary (~482/981 runners in a typical snapshot).
- **Pass A — form backfill** (every 10 min via `run_swarm_loop`, started by `AdaptiveOddsMonitor` alongside heartbeat):
  - Deterministic **field blurb** (zero cost) built from live runner fields — form string, draw, age/weight, jockey, trainer, odds — for every runner missing `timeForm`, in every region.
  - **Web-grounded Groq summary** strictly gated to aiSelections + movers + odds ≤ 6.0; capped at 6 Groq calls/cycle; cached per horse+date.
  - Persisted to ChromaDB `form_insights` (`type:"racing_insight"`, `region`, `source:"field_only"|"web"`, `ts`) + `data/swarm_insights.json`; agent notes appended via `curated_memory`.
  - Chroma freshness gate skips horses already holding today's insight (no double spend).
- **Region detection**: from Betway display prefix (`"USA: Saratoga"`) with course-keyword fallbacks — USA, Japan, South Africa, UK/IRE, Australia, New Zealand, France, Hong Kong, UAE.
- **Snapshot enrichment**: `enrich_snapshot_with_insights()` runs inline in every monitor cycle (before `set_snapshot`/SSE push), injecting `region` / `swarmInsight` / `insightSource` onto each runner.

### 🖥️ HUD Insight Surfaces (v10.2 PRO, sw v2.4.0)

- **RaceCard**: region chip (purple) + expandable insight rows — 🔥 Timeform (UK/IRE) or 🌐 Swarm (all other regions) with Show full/less toggle.
- **Market Movers**: swarm insight strip + reliability badges (✅ Verified = web-grounded, ⚠️ Baseline = field-only) + region chips.
- **Predictor**: `LiveMarketStrip` extended with region + swarm insight + reliability badges; new `InsightStrip` in expanded prediction cards and detail modal.
- **News tab**: new sidebar item (`/news`) — thumbnail grid via lazy image proxy, source/region badges, relative timestamps, SSE live updates + REST fallback.
- Types: `Runner` gains `region?/swarmInsight?/insightSource?/insightTs?`; new `NewsItem`; `HUDState.news`.

### 🔌 Backend plumbing

- `GET /api/news` + `GET /api/news/images?url=` added to `monitoring.py` routes; both plus the SSE stream are in `SAFE_PATHS` (EventSource can't send custom headers).
- Image proxy: allow-listed CDN hosts only, sha256-keyed disk cache (7-day TTL), `Cache-Control: public, max-age=86400, stale-while-revalidate`.
- SSE stream gained `event: news` (hash-check pattern shared with market-movers/predictor/results).
- New data paths in `config/paths.py`: `NEWS_PATH`, `NEWS_IMAGES_DIR`, `SWARM_INSIGHTS_PATH`.

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
