# Tasks: fix-stale-race-resurrection

## 1. Single sanctioned snapshot writer

- [x] 1.1 Create `core_agent/core/snapshot_writer.py` with `sanitize_snapshot` / `write_market_snapshot` (drop `isFinished`, prune via `_close_overdue_races`, normalise `en`, stamp `timestamp` + `snapshot_source`, atomic write, refresh memory cache); verify `python3 -c "from core_agent.core.snapshot_writer import write_market_snapshot"`
- [x] 1.2 Route the continuous scan through it: `scheduler._continuous_scan_async` replaces its raw `json.dump` with `write_market_snapshot(snapshot, source="scheduler_scan")`; verify no `open(...,"w")` writes to the snapshot path remain outside the writer
- [x] 1.3 Route the daily scan through it: `strike_tips` uses `write_market_snapshot(snapshot, source="daily_scan")`

## 2. Per-race expiry contract

- [x] 2.1 `_close_overdue_races` stamps `expires_at` (off-time + grace, epoch secs) on survivors and clears stale `first_seen`; verify `pytest core_agent/tests/test_snapshot_integrity.py -k closer`
- [x] 2.2 `snapshot_writer` fallback prune (degraded env without the monitor import) stamps `expires_at` too; verify the standalone simulation (46-race raw card → 1 live race, `expires_at` present)

## 3. Snapshot cache ingress sanitization + freshness metadata

- [x] 3.1 `snapshot_cache.set_snapshot(data, source, written_at)` sanitizes before storing; `get_snapshot()` disk path routes through it; `disk_refresh_loop` passes `source="disk-poll"` + file mtime
- [x] 3.2 `ensure_populated()` Betway stopgap reports post-prune counts and a source
- [x] 3.3 Add `get_snapshot_meta()` (`source`, `written_at`, `age_secs`); verify `pytest core_agent/tests/test_snapshot_integrity.py -k set_snapshot`

## 4. Betfair rolling cache

- [x] 4.1 Replace the 1 h all-or-nothing last-good file with the per-race rolling cache (`_load_bf_cache`, `_save_bf_cache`, `_prune_bf_events`, `_bf_cache_replay`, `BF_GHOST_GRACE_SECS`, `BF_ENTRY_TTL_SECS`) plus back-compat for pre-rolling files
- [x] 4.2 Fetch success upserts markets with `_bf_cached_at`; failure/empty replays pruned survivors with `cached: true`; all-expired cache → empty snapshot + `BETFAIR_CACHE_STALE`
- [x] 4.3 Remove the duplicate `_off_epoch_ms_from_market` definition in `betfair_sa.py`; verify `pytest core_agent/tests/test_betfair_sa.py`

## 5. Edge + HUD

- [x] 5.1 Worker `/api/ingest-snapshot`: prune at ingest, KV TTL 300 → 900 s
- [x] 5.2 Worker `/api/racing/odds` (full + per-race): prune `isFinished`/expired on read
- [x] 5.3 DataBridge: drop expired races at ingestion; refresh immediately (reset backoff) on `visibilitychange`/`focus`; verify `npx tsc --noEmit` exits 0 in `cloudflare_mcp_edge/` and `strike-tips-hud/`

## 6. Freshness visibility

- [x] 6.1 `/api/monitoring/snapshot` and `/snapshot-hash` return `snapshot_age_secs` + `snapshot_source`
- [x] 6.2 `/api/system/vitals` gains the "ODDS MONITOR (5-MIN CRON)" row (races, LIVE/STALE, age, source)
- [x] 6.3 Each monitor cycle emits one telemetry event and one `SYNC_COMPLETE` healing event (both `run()` and `run_single_cycle()`)

## 7. Tests + verification

- [x] 7.1 New `core_agent/tests/test_snapshot_integrity.py` (13 tests) covering sanitize, `expires_at`, sanctioned write, ingress sanitization and the Betfair cache state machine — **13 passed**
- [x] 7.2 Regression suites green: `test_odds_monitor_closer.py`, `test_betfair_sa.py`, `test_settlement_chain.py` — **80 passed, 1 skipped**
- [x] 7.3 Full suite: **287 passed, 1 skipped**; the only failures are the 4 pre-existing Docker-only `test_security_hardening.py` items (`ModuleNotFoundError: fastapi` on this host)
- [x] 7.4 End-to-end simulation: raw 46-race bundle (1 live / 40 finished / 5 overdue) → file, memory cache and legacy-write path all serve exactly the 1 live race with `expires_at`
- [x] 7.5 `openspec validate --all` green (30 specs + this change)
