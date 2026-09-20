# Tasks: fix-monitor-stall-resurrection

## 1. Betway leg guard

- [x] 1.1 In `run_single_cycle()`: wrap `state = await bw_task` — on exception or unusable state, reload previous snapshot from `MARKET_SNAPSHOT_PATH`; on success path stamp `stale=False` removal (clear any prior `stale`/`stale_since` keys)
- [x] 1.2 Stamp reused state `stale: true` + `stale_since` (keep original `timestamp`); write `BETWAY_FETCH_FAIL` healing event via `_write_healing_event`
- [x] 1.3 Unreadable previous file → synthesize empty events state (cycle continues, merges/closing still run)

## 2. Closer correctness

- [x] 2.1 `_close_overdue_races()`: prefer `bf_off_time` (SAST→UTC −2 h) over `t`/`st`; unparseable converted time falls back to Betway time
- [x] 2.2 Add `first_seen` stamping for events with no parseable time from any source; drop when older than 6 h (TTL constant, module-level for tests)
- [x] 2.3 Keep existing `isFinished` and 5-min grace behavior unchanged for parseable times

## 3. Stall detection

- [x] 3.1 At cycle start (before fetch), read previous snapshot `timestamp`; gap > 15 min → `MONITOR_STALL` healing event; threshold as module constant

## 4. Tests + verification

- [x] 4.1 Unit tests: Betway-fail fallback reuses previous file + stamps `stale` (fetch stubbed to raise); empty-file fallback synthesizes empty state
- [x] 4.2 Unit tests: closer drops race via `bf_off_time` with placeholder Betway `t`; closer drops unparseable-time race past `first_seen` TTL; keeps fresh race
- [x] 4.3 `MONITOR_STALL` fires at 16-min gap, silent at 10-min gap
- [x] 4.4 Full suite green (`pytest`) + `openspec validate --all` green — **host suite green** (274 passed; 4 pre-existing fastapi-missing items are Docker-only deps). Container suite carries a **pre-existing pytest capture bug** (`ValueError: I/O operation on closed file` cascades through fixture-heavy files): proven environmental via `-s` run (settlement chain 42/42) and host/container A-B; not related to this change. Targeted container runs green: closer file 18/18, security 6/6.

## Verification

- `pytest core_agent/tests/test_odds_monitor_closer.py -v` (new) plus full suite
- Evidence anchors: unguarded leg at `adaptive_odds_monitor.py:764`, closer at `:89`, `bf_off_time` stamp at `:308`
- Live check after deploy: dashboard event count reflects only post-off races; healing log shows `BETWAY_FETCH_FAIL`/`MONITOR_STALL` only when they actually occur