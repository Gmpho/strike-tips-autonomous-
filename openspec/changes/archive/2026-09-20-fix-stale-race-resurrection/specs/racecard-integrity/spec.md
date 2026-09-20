# racecard-integrity — ADDED Requirements

## ADDED Requirements

### Requirement: Single sanctioned snapshot writer

Every writer of `market_snapshot_latest.json` SHALL route through
`write_market_snapshot` (`core_agent/core/snapshot_writer.py`), which drops
`isFinished` races, prunes races past their off-time, normalises event names,
stamps `timestamp` + `snapshot_source`, and refreshes the in-memory snapshot
cache. Direct `json.dump` writes to that path are forbidden — the raw Betway
bundle may only exist in memory.

#### Scenario: Continuous scan refreshes the HUD card

- **WHEN** the scheduler's continuous scan holds a raw Betway snapshot with 40 finished races and 1 live race
- **THEN** the file on disk contains only the live race, carries a fresh `timestamp` and `snapshot_source="scheduler_scan"`, and the in-memory snapshot cache matches the file

#### Scenario: Daily scan writes the card

- **WHEN** the daily scan persists its gate snapshot
- **THEN** it calls `write_market_snapshot(..., source="daily_scan")` and the printed count reflects post-prune races

### Requirement: Per-race expiry stamp

`_close_overdue_races` SHALL stamp every surviving race with `expires_at`
(epoch seconds = off-time + grace window) and SHALL remove any stale
`first_seen` stamp; races without a parseable off-time SHALL keep the
`first_seen` TTL behaviour instead. Readers SHALL treat `expires_at` as
authoritative for dropping a race that finished after the snapshot was written.

#### Scenario: Snapshot served minutes after it was written

- **WHEN** a reader loads a snapshot whose live race has `expires_at` in the past
- **THEN** the reader drops that race without needing to parse race times

#### Scenario: Degraded environment without the monitor import

- **WHEN** the closer cannot be imported and the local fallback prune runs
- **THEN** surviving races are still stamped with `expires_at`

### Requirement: Snapshot-cache ingress sanitization

`snapshot_cache.set_snapshot` SHALL sanitize every payload before storing it
(drop `isFinished`, prune overdue races via the sanctioned writer) and SHALL
record the payload's `source` and write time, exposed through
`get_snapshot_meta()` as `source`, `written_at` and `age_secs`.

#### Scenario: Legacy raw write reaches the reader

- **WHEN** a 46-race raw bundle (1 live, 40 finished, 5 overdue) is stored through `set_snapshot`
- **THEN** `get_snapshot()` returns only the live race and `get_snapshot_meta()["source"]` names the writer

#### Scenario: Disk poll reload

- **WHEN** `disk_refresh_loop` detects a newer `market_snapshot_latest.json`
- **THEN** it reloads through `set_snapshot(..., source="disk-poll", written_at=<file mtime>)` and logs the post-prune event count

### Requirement: Betfair rolling form cache

The Betfair SA form feed SHALL be cached per race, not per file: each
successful fetch upserts its markets into the rolling cache; a failed or empty
fetch replays that cache **after** dropping markets whose off-time passed
(beyond the 5-minute grace) and entries not refreshed for 6 hours. A cache with
no usable entries SHALL yield an empty snapshot plus a `BETFAIR_CACHE_STALE`
healing event rather than re-injecting finished markets.

#### Scenario: Betfair fetch fails mid-card

- **WHEN** `get_form_format()` raises while the cache holds one upcoming and one finished market
- **THEN** the merge receives only the upcoming market with `cached: true`, and the finished market is pruned from the cache file

#### Scenario: Cache holds only finished markets

- **WHEN** every cached market's off-time has passed
- **THEN** the cycle returns an empty snapshot, writes `BETFAIR_CACHE_STALE`, and Betfair fields stay absent rather than resurrecting ghosts
