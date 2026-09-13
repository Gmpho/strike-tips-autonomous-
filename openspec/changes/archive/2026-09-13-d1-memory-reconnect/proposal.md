## Why

D1 `form_insights` froze Jun-2026 (no backend caller left for `/api/ingest-insight`), silently killing `search_past_races` depth and the "free feeds → learning memory" promise. While reconnecting, found two more live defects: the rotation left the monitor pushing with a stale second key (401s), and the snapshot fan-out did ~130 KV puts per push against a 1k/day quota (dead by ~01:00 daily).

## What Changes

* `core_agent/core/cf_push.py`: single helper for all worker pushes — STRIKE-first single-key discipline, 401 retry with legacy key, never raises.
* Morning scan mirrors official cards to D1; settlement mirrors every settled outcome to D1 (doc conventions match existing rows).
* Worker `ingest-snapshot`: single put + write-gate (skip when unchanged); per-track odds reads filter the full snapshot in code.
* Monitor both push sites use the helper.

## Capabilities

### New Capabilities
- `d1-memory-pipeline`: scan + settle mirrors into D1 form_insights.

### Modified Capabilities
- `atr-fetch-resilience`: KV snapshot push budget (single-put + write-gate).

## Impact

* `core_agent/core/cf_push.py` (new), `adaptive_odds_monitor.py`, `strike_tips.py`, `result_tracker.py`
* `cloudflare_mcp_edge/src/index.ts` (ingest + odds reader)
* Tests: `test_cf_push.py` (10). Verify after UTC midnight: KV populated, D1 growing on scans/settles.
