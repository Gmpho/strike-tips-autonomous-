# Strike Tips: Production Roadmap & Implementation Progress

## ✅ Accomplished (Completed Tasks)

### 1. Infrastructure & Security
- [x] **API Security**: Implemented global `AuthMiddleware` requiring `X-API-KEY` for all routes.
- [x] **MCP Integration**: Created dynamic `mcp_server.py` that auto-discovers all 11 MAF tools.
- [x] **Container Connectivity**: Solved Docker-host networking issues to ensure Ollama is accessible (`OLLAMA_HOST=0.0.0.0`).
- [x] **Documentation**: Created full `MCP_INTEGRATION_GUIDE.md` and `security-framework.md`.

### 2. Analysis Pipeline
- [x] **Batch Processing**: Refactored `strike_tips.py` from recursive individual tool calls to a streamlined Batch AI Analysis pattern.
- [x] **Loop Prevention**: Implemented `_processing_tracks` locking and non-recursive dispatch logic to stabilize scan outputs.
- [x] **JSON Enforcement**: Forced AI output to structured JSON via prompt engineering to prevent parser crashes.

### 3. Data Ingestion
- [x] **PDF Harvester Patch**: Fixed URL formatting to match 4Racing CDN conventions (using `{track}@{date}.pdf` with `YYYY.MM.DD` format).
- [x] **Live/PDF Hybrid**: Configured scraper to prioritize Live JSON API data, using PDF only as a robust secondary source.
- [x] **Resilience**: Added automated pre-warming for future racing dates at 8:00 PM daily.

---

## 🛠️ Next Phase: Live Market Integration Plan

## Objective
To move from "Flat 5.0 Odds" to "Dynamic Market Odds" by injecting real-time Betway/Tab snapshots into the analysis pipeline.

## Implementation Steps

### Phase 1: Odds Injection Logic
- [ ] Create `get_live_odds` helper in `core_agent/skills/parsers/tab4racing.py` that reads from `data/market_snapshot_latest.json`.
- [ ] Update `TAB4RacingScraper` to inject these live odds into `ScrapedRunner` objects during the scrape process.

### Phase 2: Workflow Automation
- [ ] Ensure `StrikeTips.scrape_and_analyze_track` utilizes the updated runner objects containing live odds.
- [ ] Verify that `RaceAnalyzer` uses these live decimal odds instead of the `5.0` default.

### Phase 3: Validation
- [ ] Verify `Fairview` scan shows distinct odds per runner instead of the flat `5.0`.
- [ ] Confirm no `ValueBet` entries are missed due to the previous static odds default.

## 🔗 Security & Keys
- Current `X-API-KEY`: `sk`
- **Remember**: Keep this key secure and rotate via `openssl rand -hex 16` if compromised.
