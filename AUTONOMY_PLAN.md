# Strike Tips — Full Autonomy Plan

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        STRIKE TIPS SYSTEM                            │
│                                                                      │
│  ┌──────────────────┐    ┌──────────────────┐    ┌───────────────┐  │
│  │  Betway API      │    │  Oddschecker      │    │  TAB4Racing   │  │
│  │  (poll 45s)      │    │  (poll 5min)      │    │  (PDF parse)  │  │
│  └────┬─────────────┘    └─────┬────────────┘    └──────┬────────┘  │
│       │                       │                        │           │
│       ▼                       ▼                        ▼           │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              AdaptiveOddsMonitor (odds-monitor)               │  │
│  │  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │  │
│  │  │ BetwayAPI   │  │ OC scraper   │  │ AlertEngine        │  │  │
│  │  │ snapshot    │  │ overlay      │  │ ├─ evaluate odds   │  │  │
│  │  └─────────────┘  └──────────────┘  │ ├─ trigger alerts  │  │  │
│  │                                     │ ├─ auto-bet        │  │  │
│  │                                     │ └─ notify Telegram │  │  │
│  │  ┌───────────────────────────────┐  └────────────────────┘  │  │
│  │  │ IntelligenceCache (baselines) │                           │  │
│  │  └───────────────────────────────┘                           │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              StrikeTips (daily scan orchestrator)             │  │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │  │
│  │  │ AI       │  │ PDF     │  │ Bankroll │  │ Learning    │ │  │
│  │  │ Analysis │  │ Harvester│  │ Governor │  │ Engine      │ │  │
│  │  └──────────┘  └──────────┘  └──────────┘  └─────────────┘ │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │              StrikeTipsScheduler (background loop)             │  │
│  │  06:00 ─ PDF grounding       21:00 ─ Learning update          │  │
│  │  11:00 ─ Daily scan          20:00 ─ EOD report               │  │
│  │  every 5min ─ ResultTracker (auto-settle)                     │  │
│  └──────────────────────────────────────────────────────────────┘  │
│                                                                      │
│  ┌─────────────────────────┐    ┌──────────────────────────────┐  │
│  │   FastAPI Server         │    │   Telegram Notifier          │  │
│  │   localhost:8000          │    │   (alerts, results, errors) │  │
│  └─────────────────────────┘    └──────────────────────────────┘  │
│                                                                      │
│  ┌──────────────────────┐    ┌─────────────────────────────────┐   │
│  │  React HUD (Vite)    │    │  ChromaDB (form insights,       │   │
│  │  localhost:5173       │    │  dreams, long-term memory)      │   │
│  └──────────────────────┘    └─────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow (Race → Bet → Settlement)

```
1. DISCOVERY
   Betway API → AdaptiveOddsMonitor syncs race data (45s loop)
   Oddschecker overlays best-odds overlay (5min loop)
   TAB PDFs → PDFHarvester → ChromaDB memory

2. ANALYSIS
   AlertEngine evaluates odds movements against baselines
   → triggers alerts for value_bet, odds_drop, threshold conditions
   Daily scan dispatches parallel AI analysis via Kimi
   → returns value_bets with edge estimates

3. BET PLACEMENT (two paths)
   Path A (live odds):   AlertEngine._maybe_auto_bet()
   Path B (daily scan):  run_daily_scan() → place_bet() for edge >= 5.5%
   Both record via BankrollGovernor.record_bet() → bet_history.json

4. SETTLEMENT
   ResultTracker searches DuckDuckGo for race results (every 5min)
   → fuzzy-matches horse names
   → StrikeTips.settle_bet()
   → updates bankroll, learning engine, Telegram notification
```

## Current Autonomy Level: ~60%

| Phase | Component | Status | Notes |
|-------|-----------|--------|-------|
| **Discovery** | Betway polling | ✅ Automated | 45s loop in odds-monitor |
| | Oddschecker overlay | ✅ Automated | 5min loop |
| | PDF harvesting | ✅ Automated | Daily schedule 06:00 |
| **Analysis** | Alert engine | ✅ Automated | Evaluates every sync cycle |
| | AI daily scan | ✅ Automated | 11:00 daily schedule |
| | Dream engine | ✅ Automated | ChromaDB every 5min |
| **Betting** | Live odds auto-bet | ✅ Automated | Edge ≥ min_edge via AlertEngine |
| | Daily scan auto-bet | ✅ Automated | **NEW** — runs after scan |
| | External exchange | ❌ Manual | Paper-only; no real API |
| **Settlement** | Auto-settlement | ✅ Automated | **NEW** — DDG search every 5min |
| | Learning update | ❌ Stubbed | `update_learning_job()` is `pass` |
| **Reporting** | EOD report | ❌ Stubbed | `_end_of_day_report()` is `pass` |
| | Continuous scanning | ❌ Stubbed | `continuous_scan_job()` is `pass` |
| **Infra** | Scheduler running | ❌ Not active | Not started from API entrypoint |
| | DuckDuckGo installed | ❌ Not in container | `duckduckgo_search` missing |
| | AlertEngine → live bet | ✅ Automated | Places to bankroll JSON |

## Remaining Gaps (Priority Order)

### P0 — Required for "hands-off" operation

1. **Install `duckduckgo_search` in container** — `ResultTracker.check_race_results_job()` runs but DDG search always returns None because the package isn't in `requirements.txt`. Fix: add `duckduckgo_search` to requirements, rebuild container.

2. **Start scheduler from API entrypoint** — The scheduler thread (`StrikeTipsScheduler.start()`) is never called. The `check_race_results_job` and other scheduled jobs don't run. Fix: start the scheduler in `api.py:startup_event()` after `brain.initialize()`.

3. **Connect AlertEngine auto-bet to strike_tips.place_bet()** — Currently `_maybe_auto_bet()` calls `bankroll.record_bet()` directly, bypassing `strike_tips.place_bet()` which handles Telegram notification and learning engine recording. Fix: route through `strike_tips.place_bet()` or call Telegram from `_maybe_auto_bet()`.

### P1 — Strongly recommended

4. **Install `duckduckgo_search` in requirements** — Required for auto-settlement to actually work. Currently `HAS_DDGS = False` in `result_tracker.py`.

5. **Start scheduler from API** — The `StrikeTipsScheduler` is never started. All scheduled jobs depend on it.

6. **Wire continuous_scan_job** — Currently `pass`. Should re-scan tracks for new races appearing mid-day (every 15min). Implement basic: for each active track, check if more races appeared.

7. **Wire update_learning_job** — Currently `pass`. Should re-analyze learning_stats.json and generate performance report. Low complexity — just plumb the existing `LearningEngine` analysis.

8. **Wire _end_of_day_report** — Currently `pass`. Should generate and send a comprehensive daily Telegram summary with P&L, win rate, ROI by track, and recommendations.

### P2 — Nice to have

9. **External exchange integration** — Real bet placement via Betway/WHR API. Requires auth tokens, stake confirmation, and race-time validation. Paper mode will remain default.

10. **MarketWatcher integration** — `MarketWatcher.watch()` exists but is standalone. It creates its own `StrikeTips` and runs a separate loop. Should either be removed or integrated into the odds-monitor pipeline.

11. **Continuous scan refinements** — Add smarter mid-day scanning that only checks tracks with upcoming races (not all tracks). Use `RaceScheduleService` to determine which tracks are racing today.

12. **ResultTracker confidence tuning** — Currently uses 0.6 threshold for fuzzy match. After collecting real settlement data, tune this threshold to balance false positives vs missed settlements.

## Implementation Estimates

| Gap | Effort | Risk | Impact |
|-----|--------|------|--------|
| Install duckduckgo_search | 5 min | Low | Auto-settlement doesn't work without it |
| Start scheduler from API | 15 min | Low | Scheduled jobs don't run |
| Wire continuous_scan_job | 30 min | Low | Catches mid-day race additions |
| Wire update_learning_job | 15 min | Low | Learning data stays fresh |
| Wire _end_of_day_report | 30 min | Low | No daily summary for review |
| Route auto-bet through place_bet() | 15 min | Low | Missing Telegram + learning feedback |
| Exchange API integration | 3-5 days | High | Enables real money betting |
| MarketWatcher integration | 1-2 hours | Medium | Cleans up redundant code |

## Key Decisions

- **Paper mode until exchange API is stable** — `paper_mode: true` in settings keeps all bets simulated
- **TAB is PDFs only** — no odds or market data from TAB; exclusively Betway + Oddschecker
- **Bankroll state is JSON + fcntl.flock** — Redis migration deferred; current throughput doesn't warrant it
- **AI analysis uses Kimi** — not Ollama; Kimi handles the parallel race analysis in daily scan
- **No pre-race countdown auto-bet** — All auto-bets fire at scan time or when odds movement triggers an alert; no scheduler-based placement at race start time
