# Proposal: fix-stale-race-resurrection

## Why

On 2026-09-20 the dashboard count oscillated all day between the live card
(~58 races) and the full morning card (126 races), with finished races
reappearing minutes after the monitor had closed them. Three independent
faults, all proven live:

1. **Two scan-side writers bypassed the monitor's pruning.** `scheduler.py`
   (continuous scan, every 15 min) and `strike_tips.py` (daily scan) dumped the
   RAW Betway bundle straight over `market_snapshot_latest.json`. The raw bundle
   carries no `timestamp`, keeps `isFinished` races and keeps races whose
   off-time passed hours ago; `disk_refresh_loop` (15 s) then re-served it to
   every HUD reader. Evidence: the monitor pushed 58 races to edge KV at
   15:20:27 while `/api/monitoring/snapshot` served 126 races with no
   `timestamp`, and the container log showed
   `snapshot-cache - INFO - Snapshot reloaded from disk (126 events)`.
2. **Betfair's fallback cache re-injected ghosts or blanked the card.**
   `betfair_form_last_good.json` was an all-or-nothing 1-hour file with no
   per-race validation: replaying it resurrected finished markets, and once it
   aged past 1 h every gear/days field vanished from the whole card until the
   next successful fetch ("Betfair data keeps disappearing and coming back").
   Healing logged `BETFAIR_EMPTY` three times that day (10:15, 12:50, 13:55).
3. **Edge KV odds expired between cron cycles.** `/api/ingest-snapshot` wrote
   with `expirationTtl: 300` — exactly the monitor period — so one late cycle
   blanked `/api/racing/odds` for readers, and nothing pruned finished races on
   read (a stale KV entry could serve the morning card for its whole TTL).

## What Changes

- **One sanctioned writer**: new `core_agent/core/snapshot_writer.py`
  (`write_market_snapshot`) drops finished + overdue races, normalises names,
  stamps `timestamp` + `snapshot_source`, and refreshes the in-memory cache.
  `scheduler.py` and `strike_tips.py` now call it instead of dumping raw JSON.
- **Per-race expiry contract**: `_close_overdue_races` stamps `expires_at`
  (epoch secs = off-time + grace) on every survivor, and `snapshot_cache`
  sanitizes on **every** ingress (`set_snapshot`), so a legacy or regressed
  writer still cannot leak finished races to the HUD, worker or Telegram.
- **Betfair rolling cache**: per-race upsert, per-race expiry (5 min post-off)
  and a 6 h no-refresh TTL replace the 1 h all-or-nothing file; the duplicated
  `_off_epoch_ms_from_market` definition is removed.
- **Edge**: snapshot KV TTL 300 → 900 s (3 cron cycles) and finished/expired
  races are pruned at ingest and on read.
- **Freshness visibility**: `/api/monitoring/snapshot*` returns
  `snapshot_age_secs` + `snapshot_source`; `/api/system/vitals` gains an
  "ODDS MONITOR (5-MIN CRON)" row (races + snapshot age); every monitor cycle
  emits a telemetry event and a `SYNC_COMPLETE` healing event so Live-Ops is
  never empty; the HUD DataBridge prunes expired races at ingestion and
  refreshes immediately on focus/visibility change.

## Capabilities

### New Requirements

- `racecard-integrity` — single sanctioned snapshot writer, per-race expiry
  stamp, snapshot-cache ingress sanitization, Betfair rolling form cache.
- `observability` — snapshot freshness is queryable; monitor cycles emit
  liveness signals.
- `cloudflare-hud-hosting` — edge odds cache outlives one missed cron cycle,
  prunes expired races, and the HUD enforces expiry client-side.

## Impact

- `core_agent/core/snapshot_writer.py` (new), `snapshot_cache.py`,
  `adaptive_odds_monitor.py`, `scheduler.py`, `strike_tips.py`,
  `routes/monitoring.py`, `skills/parsers/betfair_sa.py`
- `cloudflare_mcp_edge/src/index.ts` (edge prune + TTL)
- `strike-tips-hud/src/engine/data-bridge.ts` (expiry prune + focus refresh)
- `core_agent/tests/test_snapshot_integrity.py` (new, 13 tests)
- No new dependencies; no Modal app/secret/schedule changes.
