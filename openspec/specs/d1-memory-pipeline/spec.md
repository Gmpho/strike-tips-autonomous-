# d1-memory-pipeline Specification

## Purpose
Keep the edge learning memory fresh: every card and every settled outcome lands in D1 automatically.

## Requirements

### Requirement: Scan card mirror

Each morning scan SHALL push one `official_card` insight per race (doc `card-{date}-{track}-r{n}`) with runners, time, and condition.

#### Scenario: Tuesday scan
- **WHEN** the morning scan completes with 25 races
- **THEN** ~25 card rows exist in D1 dated that day

### Requirement: Settlement result mirror

Every auto-settled bet SHALL push one `race_result` insight (doc `result-{date}-{track}-r{n}-{bet_id}`) with outcome, stake, and return.

#### Scenario: Settle run
- **WHEN** 14 bets settle in a cycle
- **THEN** 14 result rows exist in D1 (best-effort; settlement never waits)

### Requirement: Pushes never break callers

All worker pushes SHALL be best-effort with short timeouts and SHALL never raise into scans, settles, or monitor cycles.

#### Scenario: Worker down
- **WHEN** the worker is unreachable during a scan
- **THEN** the scan completes normally and logs a debug line
