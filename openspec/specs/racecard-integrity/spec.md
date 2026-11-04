# racecard-integrity Specification

## Purpose
Guarantee every card, play, and ticket the system publishes belongs to today's actual meetings.

## Requirements

### Requirement: Future-meeting gate

The morning scan SHALL drop any track Betfair proves is not running today (course known, none of its event dates is today). Unknown courses fail open. Dropped tracks log loudly with the offending dates.

#### Scenario: Thursday card harvested Sunday
- **WHEN** TAB serves Thursday Vaal during Sunday's scan and Betfair dates Vaal 2026-09-17
- **THEN** Vaal leaves Sunday's scan with zero races and a gate log line

### Requirement: Per-track exotic attribution

Exotic plays SHALL be built once per non-empty track and stamped with that track only; first-dict-key labelling is forbidden.

#### Scenario: Multi-track scan day
- **WHEN** the scan holds Scottsville, Durbanville, and Vaal cards
- **THEN** no play carries a track it was not built from

### Requirement: Phantom-meeting guard

A play SHALL reach the board only when at least half its bankers run at its track in today's snapshot; otherwise it is dropped as a suspected phantom.

#### Scenario: Mislabeled Thursday play
- **WHEN** a "turffontein" play's bankers appear nowhere in Turffontein's snapshot runners
- **THEN** the play never reaches the board or auto-bet

### Requirement: Snapshot-cycle failure fallback

The odds-monitor cycle SHALL NOT lose the last-good market snapshot when its base feed (Betway) fails: it SHALL reuse the previous snapshot from disk, stamp it `stale: true` with `stale_since`, record a `BETWAY_FETCH_FAIL` healing event, and still run merges/closing on the reused state so the file keeps advancing with honest staleness metadata.

#### Scenario: Betway wall during racing hours
- **WHEN** `betway.get_snapshot_format()` raises or returns unusable data in a cycle
- **THEN** the cycle writes a fresh snapshot file whose `stale` flag is true and carries the same race set as the previous good snapshot, and a `BETWAY_FETCH_FAIL` healing event exists
- **AND** no `None` early-return occurs (downstream merges, closing, and KV push still execute)

### Requirement: Authoritative off-time closing

`_close_overdue_races` SHALL prefer an event's `bf_off_time` (stamped by the Betfair merge; SAST wall clock) over Betway display times when deciding whether a race is past off, converting SAST→UTC before comparing against the container clock. Races past off by more than the grace window SHALL be dropped regardless of which source provided the time.

#### Scenario: UK/IRE race Betway never finishes
- **WHEN** a race has no `isFinished` flag, a placeholder Betway time, and a `bf_off_time` more than 5 minutes in the past
- **THEN** the race is removed from the snapshot in that cycle

### Requirement: Unparseable-off-time TTL

A race with no parseable off-time from any source SHALL be stamped `first_seen` on first observation and dropped once that stamp exceeds a 6-hour TTL, so unfinished/unparseable races cannot persist indefinitely.

#### Scenario: Race with no usable time hoards all day
- **WHEN** a race lacking any parseable off-time has been observed for more than 6 hours
- **THEN** it is dropped from the snapshot

### Requirement: Monitor stall detection

At the start of each successful cycle the monitor SHALL compare the previous snapshot's `timestamp` to the current time; when the gap exceeds 15 minutes it SHALL record a `MONITOR_STALL` healing event (internal healing log only — no Telegram, no frontend changes).

#### Scenario: Cron misses for an hour
- **WHEN** the next successful cycle finds the previous snapshot timestamp 60 minutes old
- **THEN** a `MONITOR_STALL` healing event records the gap, and the cycle proceeds normally

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
