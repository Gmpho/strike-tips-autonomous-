# racecard-integrity — ADDED Requirements

## ADDED Requirements

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