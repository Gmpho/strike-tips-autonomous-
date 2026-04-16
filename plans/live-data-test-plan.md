# Test Plan: Live Data Integration & Security Verification

## Objective
To verify that the Strike Tips engine can successfully fetch real-time racing data from TAB4Racing, analyze it, and interact with the secure API/MCP interface.

## 1. Prerequisites
- [ ] Backend services (`strike-bot`, `odds-monitor`) are running in Docker.
- [ ] Environment variables (`GEMINI_API_KEY`, `GROQ_API_KEY`) are valid.
- [ ] `X-API-KEY` is configured in `.env`.

## 2. Test Phases

### Phase A: Live Scrape & Data Extraction
- **Action**: Trigger a real-time scan for a known active track (e.g., 'turffontein').
- **Command**: `docker exec strike-bot-new python strike_tips.py track --track turffontein`
- **Success Criteria**: 
  - [ ] API returns valid race card JSON.
  - [ ] PDF Harvester correctly pre-warms the cache.
  - [ ] Scraper handles track codes (XTD) correctly.

### Phase B: Value Analysis Workflow
- **Action**: Evaluate a race result for value.
- **Command**: `curl -H "X-API-KEY: <YOUR_KEY>" http://localhost:8000/api/racing/scan`
- **Success Criteria**:
  - [ ] Analysis completes without error.
  - [ ] Probability estimates are calculated for runners.
  - [ ] Value bets (edge > 5%) are identified.

### Phase C: Secure Tool Execution (MCP/API)
- **Action**: Test the protected API and tool-calling capability.
- **Command**: `curl -H "X-API-KEY: <YOUR_KEY>" http://localhost:8000/api/agent/tools`
- **Success Criteria**:
  - [ ] 200 OK received.
  - [ ] Correct tool list returned (11 tools).

### Phase D: End-to-End Betting Governor Check
- **Action**: Attempt to record a selection (simulated).
- **Command**: Use the `/api/betting/place` route (via `curl`) with a known valid race.
- **Success Criteria**:
  - [ ] Bankroll Governor validates stake size (max 5%).
  - [ ] Bet record created in `data/bet_history.json`.

## 3. Data Validation
- [ ] Verify `data/daily_scan_<date>.json` is populated.
- [ ] Verify `data/bankroll_state.json` reflects any simulated bet activity.

## 4. Rollback / Emergency
- If data corruption occurs, restore from `data/bankroll_state.json.bak`.
- If scrapers fail due to site changes, revert to `SelfHealingParser` status reporting.
