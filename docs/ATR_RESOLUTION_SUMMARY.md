# ATR Data Resolution Summary
## Problem
The ATR (At The Races) data was experiencing a cycle of appearing then disappearing in the HUD frontend. This was caused by:
1. Cloudflare/Fastly challenges blocking HTTP requests
2. ATR HTML changes breaking selectors
3. Odds monitor overwriting good data with empty arrays when API returned blank

## Solution Implemented
### 1. Resilient Fetching Mechanism
- **Tiered fallback system** in `core_agent/skills/parsers/attheraces_api.py`:
  - Primary: StealthyFetcher (headless Chromium + Cloudflare solver + persistent browser profile)
  - Secondary: Fetcher.get (HTTP impersonation with realistic headers)
  - Fallback: None (returns empty data but doesn't crash)
- Added `msgspec>=0.19.0` to requirements.txt for StealthyFetcher dependency
- Persistent browser profile stored at `/app/data/browser_profile` to maintain session cookies

### 2. Self-Healing Selectors
- Enabled `adaptive=True` on Selector initialization (Scrapling v0.4.8 feature)
- This allows automatic relocation of elements when ATR HTML changes (40% similarity threshold)
- Removed redundant `adaptive=True` from individual `.css()` calls to eliminate warnings

### 3. Data Integrity Protection
- Existing guard in `core_agent/core/adaptive_odds_monitor.py`: `if atr_data:` before writing snapshots
- Prevents overwriting good data with empty arrays when ATR temporarily returns blank

### 4. Deployment Updates
- Rebuilt odds-monitor container to incorporate code and dependency changes
- Restarted both odds-monitor and strike-bot containers to apply fixes

## Verification Results
- **Predictor**: 39 items rendering in HUD
- **Market Movers**: 523 items rendering in HUD  
- **Results**: 579 items rendering in HUD
- Data persists through refresh cycles without disappearing
- No adaptive selector warnings in container logs
- System self-heals from Cloudflare challenges and HTML changes

## Extended Features Added

### 5. MAF Tool Integration (Agent Access)
- **New tools in `core_agent/tools/maf_tool_registry.py`** (now 15 total):
  - `get_atr_market_movers` — ATR market movers (523 items)
  - `get_atr_predictor` — ATR AI predictions (39 items)
  - `get_atr_results` — ATR race results (579 items)
  - `get_dream_context` — Agent's background reasoning from Honcho/ChromaDB
- Agent can now query live ATR data directly via tools

### 6. TTL-Based Cleanup
- **`_cleanup_atr_snapshots(ttl_days=7)`** in `adaptive_odds_monitor.py`
- Removes backup/old snapshot copies older than 7 days
- Keeps main snapshot files (`atr_*_snapshot.json`) intact
- Runs on each sync cycle

### 7. Staleness Alerting
- **`_check_atr_staleness(max_age_hours=3)`** in `adaptive_odds_monitor.py`
- Checks timestamp in each snapshot against 3-hour threshold
- Fires alert via AlertEngine if any snapshot exceeds threshold
- One-time alert deduplication to avoid spam
- Alert includes details: which snapshot, age, last update time

## Key Files Modified
1. `core_agent/skills/parsers/attheraces_api.py` - Tiered fetching + adaptive selectors
2. `requirements.txt` - Added msgspec dependency
3. `Dockerfile.odds` - Unchanged but container rebuilt to pick up updates
4. `core_agent/core/adaptive_odds_monitor.py` - Data integrity guard + TTL cleanup + staleness alerts
5. `core_agent/tools/maf_tool_registry.py` - 4 new ATR/dream tools (15 total)
6. `docs/AGENTS.md` - Updated tool registry documentation
7. `README.md` - Added ATR to architecture diagram

## Current State
The ATR data flow is now stable and resilient:
- Fetching succeeds via StealthyFetcher when challenged
- Selectors auto-adjust to minor HTML changes
- Good data snapshots are preserved during temporary blanks
- Frontend views consistently display live ATR data
- Agent has direct tool access to all ATR endpoints + dream context
- Automatic TTL cleanup prevents disk bloat
- Proactive staleness alerts catch fetch failures early
- No more disappearing data cycle observed