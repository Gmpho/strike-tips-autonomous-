# Proposal: fix-monitor-stall-resurrection

## Why

Three production incidents on 2026-09-19 traced to the odds-monitor snapshot pipeline:

1. **~10-hour dashboard freeze.** `run_odds_monitor` (5-min Modal cron) is the *only* writer of `market_snapshot_latest.json`; news/swarm/dream ride along only every 6th tick (~30 min) after the dedicated cron was cut for Modal's free-tier 5-cron limit. When the cron stalls (Betway wall, spawn failure, redeploy), every consumer — dashboard, news, healing, live-ops, KV edge odds (TTL 300 s) — serves the stale file indefinitely with no signal. Precedent recorded in `modal_app.py` ("Sep-2026: LiveOps showed swarm/news idle, news 9h").
2. **Silent freeze on Betway failure.** In `AdaptiveOddsMonitor.run_single_cycle()`, the Betway leg (`state = await bw_task`) is the only unguarded fetch — Racing-Odds and Betfair legs are try-wrapped. A Betway wall/exception returns `None` before any disk write or KV push, so the freeze leaves no trace and no fallback.
3. **Finished-race resurrection / hoarding.** `_close_overdue_races()` drops races only via Betway `isFinished` or a parseable off-time >5 min past. UK/IRE races commonly never set `isFinished` (docstring says so), and races with missing/placeholder times are silently *skipped* by the closer — they accumulate all day (30 → 45 events), then vanish in bulk when Betway rotates the card. Meanwhile the Betfair merge already stamps the exact `bf_off_time` on events (added precisely because Betway display times can be placeholders) — **but the closer never reads it.**

## What Changes

- Guard the Betway leg: on failure, reuse the last-good snapshot from disk stamped `stale: true` + `stale_since`, write a `BETWAY_FETCH_FAIL` healing event, and let the cycle continue (merges/closer still run on the reused state).
- Upgrade `_close_overdue_races()`: prefer `bf_off_time` (converted SAST→UTC) over display times; close races past off regardless of source; give races with no parseable time a `first_seen` TTL (default 6 h) so nothing persists all day.
- Detect stalls internally: when a cycle starts and the previous snapshot's timestamp is >15 min old, write a `MONITOR_STALL` healing event (visible in the existing Healing panel).
- **No Telegram notifications** (user explicitly declined), **no HUD changes**, no new alert channels.

## Capabilities

### New Requirements

- `racecard-integrity` — snapshot-cycle failure fallback, authoritative off-time closing, unparseable-off-time TTL, monitor stall detection.

## Impact

- `core_agent/core/adaptive_odds_monitor.py` (cycle guard, closer, first_seen TTL, stall check)
- `core_agent/tests/` (unit tests for closer semantics + fallback reuse; existing closer tests updated)
- No API routes, no frontend, no Modal app changes.