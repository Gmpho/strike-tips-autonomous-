# Design: fix-stale-race-resurrection

## Context

`market_snapshot_latest.json` is the single source the HUD, the edge KV push and
Telegram read. It had **three writers** with different rules:

| Writer | Cadence | Pruning | `timestamp` |
|--------|---------|---------|-------------|
| `AdaptiveOddsMonitor` (Modal cron) | 5 min | yes (closer + TTLs) | yes |
| `scheduler._continuous_scan_async` (serve container) | 15 min | none | no |
| `strike_tips` daily scan (serve container) | daily | none | no |

The two scan writers raced the monitor: whichever ran last owned the file for
the next 15 s disk poll. Live measurement (2026-09-20 15:21): the monitor's KV
push held 58 races, `/api/monitoring/snapshot` served 126 races with no
`timestamp`, and the log line `Snapshot reloaded from disk (126 events)`
confirmed the poll had ingested the scan-side dump.

Independently, the Betfair fallback (`betfair_form_last_good.json`) was one
file with one age limit: 1 h. Replaying it re-injected finished markets; ageing
past it removed every gear/days field from the card until the next success.

## Goals / Non-Goals

**Goals**

- One pruning rule for every writer; current races only, on every read path.
- A single, cheap way for *any* reader to know a race is finished: `expires_at`.
- Betfair gear/days stay stable while a race is upcoming and vanish once it runs.
- Make feed freshness observable (age, source, cycle liveness) so "is it current?"
  is answerable without shell access.

**Non-Goals**

- No Modal schedule/secret/app changes; no new dependencies.
- Not changing settlement, bankroll, or the value-bet pipeline.
- No SSE revival (retired 2026-09-15 for cost reasons).

## Decisions

### D1 — A single sanctioned writer module

`core_agent/core/snapshot_writer.py` owns `write_market_snapshot()`; it prunes,
stamps and refreshes the cache, and is idempotent. Scan-side callers keep their
own control flow (raw snapshot in memory) but can no longer decide what reaches
disk. A defensive local prune inside the module keeps the contract even when the
monitor package cannot be imported (bare envs, partial installs).

### D2 — `expires_at` instead of re-deriving times per client

Time zones were the trap: Betway times are UTC walls, `bf_off_time` is a SAST
wall, and clients run in SAST. Publishing one absolute `expires_at` per race
removes all client-side time math: the worker compares epoch seconds, the HUD
compares epoch seconds, and both stay correct for a snapshot written minutes ago.
Readers that see no `expires_at` (older payloads) fall back to `isFinished`-only.

### D3 — Sanitize at ingress, not only at write

`snapshot_cache.set_snapshot()` sanitizes every payload, so even a future writer
that bypasses `write_market_snapshot` cannot leak finished races into the served
snapshot. This is the layer that would have contained today's incident on its own.

### D4 — Betfair cache keyed per race

A file-level TTL is the wrong granularity: a cached market is useful exactly
while its race is upcoming. The rolling cache stores markets keyed by market id
with `_bf_cached_at`, prunes on off-time (+5 min grace) and on a 6 h
no-refresh TTL, and replays the survivors when a fetch fails. Result: no ghost
re-injection, no gear/days flicker, and `BETFAIR_CACHE_STALE` only when the
cache is genuinely unusable.

### D5 — KV TTL 900 s + edge pruning

TTL == cron period guaranteed a race: a 30 s delay expired the key. 3 cycles of
slack plus read-time pruning means a stale entry degrades gracefully (fewer
races, never wrong ones).

### D6 — Freshness is a first-class field

`snapshot_age_secs` + `snapshot_source` on the monitoring endpoints, a monitor
row in vitals, one telemetry event and one `SYNC_COMPLETE` healing event per
cycle. These are cheap (a dict copy and one append) and they replace "why is
Live-Ops showing this morning?" investigations.

## Risks and Mitigations

- **Prune aggressiveness closes live races.** Grace stays at 2 min for the
  monitor and 5 min for Betfair markets; `expires_at` is computed from the same
  off-time the closer already trusted, so behaviour changes only where the old
  code would have kept a race past its off.
- **`set_snapshot` cost.** One shallow copy per event per ingress (≤ ~150 races,
  every 15 s) — negligible versus the JSON parse already done.
- **Losing raw scan data.** The raw bundle is still fetched and used in memory by
  the scan; only the persisted copy is pruned.
- **Rollback.** All changes are additive fields plus a new module; reverting the
  two scan-side call sites restores previous behaviour without data migration.
