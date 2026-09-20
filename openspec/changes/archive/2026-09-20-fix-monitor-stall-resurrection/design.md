# Design: fix-monitor-stall-resurrection

## Context

All evidence is from tonight's code reading (no speculation):
- `run_single_cycle()` (`core_agent/core/adaptive_odds_monitor.py:751`): only `ro_task`/`bf_task` are try-wrapped; `state = await bw_task` propagates exceptions to the outer handler which returns `None` before `_atomic_write_json(MARKET_SNAPSHOT_PATH, ...)`.
- `_close_overdue_races()` (line 89): `off_time = _parse_race_off_time(t_str) if t_str else None` — races with placeholder times are silently kept; the docstring of the Betfair merge (line 308) confirms it stamps `event["bf_off_time"]` (SAST wall, per `_sast_wall()` line ~222) — currently unread by the closer.
- `_fetch_betfair_form_safely()` (line 654) already implements the last-good pattern for Betfair (`_bf_last_good_path`, 6 h max age) — the Betway guard reuses the same shape for the snapshot itself.
- Healing events: `_write_healing_event(action, details, agent, status)` (line 595) writes `data/healing_events.json` (last 50) — the user's existing internal visibility channel. Explicitly NO Telegram (user declined), no HUD changes.

## Goals / Non-Goals

- Goals: snapshot file never freezes silently; finished races cannot hoard; stalls are visible in Healing.
- Non-Goals: Telegram/webhook alerts, HUD staleness badges, multi-writer redundancy, changing cron cadence, KV TTL changes.

## Decisions

### D1: Betway leg guard = last-good disk reuse (not in-memory)
On Betway failure, reload the previous `market_snapshot_latest.json` (the same file the closer/merges would rewrite) instead of adding another cache file. Stamp `state["stale"] = True`, `state["stale_since"] = now.isoformat()` (keep the original `timestamp` field untouched so stall math stays honest). Continue the cycle: merges may still enrich, closing still prunes. If the file itself is unreadable, synthesize `{"events": {}, "count": 0}` — a wiped board is better than a lying one, and the healing event says why.

### D2: Closer time preference: `bf_off_time` → `t`/`st`
`bf_off_time` is a SAST wall clock ("14:40"); the container runs UTC. Convert SAST→UTC by subtracting 2 h (no DST in SA — mirrors `_sast_wall`'s inverse). If conversion fails, fall through to Betway time. Grace window stays 5 min.

### D3: `first_seen` TTL for unparseable races
On first sight of a race with no parseable time from any source, stamp `first_seen` (epoch) into the event. When `now - first_seen > 6 h`, drop it. Stamp is written into the snapshot so it survives cycle-to-cycle via the file itself. Skip stamping for races that DO have a parseable time (no pollution of good events).

### D4: Stall detection is read-only at cycle start
Before fetching, read the previous file's `timestamp`; if >15 min old, `_write_healing_event("MONITOR_STALL", ...)`. Runs inside the successful path only (a fully dead monitor writes nothing by definition — the absence of healing events + frozen file is the signal that motivates D1's honest staleness stamp).

## Risks / Trade-offs

- Reused last-good keeps merging fresh RO/BF data onto stale Betway odds — acceptable: stamped `stale: true`, and 5-min staleness beats a frozen 10-hour board.
- SAST→UTC conversion assumes the container stays UTC — asserted in tests.
- `first_seen` TTL could drop a race whose time data arrives broken upstream for 6 h — acceptable; such a race is unbettable anyway.

## Migration / Rollout

Single deploy via `modal deploy`; no data migration. Rollback = redeploy previous image. Tests run in-container (`docker exec strike-bot pytest`) where available, else host pytest.