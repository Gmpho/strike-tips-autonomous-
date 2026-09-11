## Purpose

Exact Betfair meeting times threaded through the system so settlement and display never rely on placeholder race times.

## ADDED Requirements

### Requirement: Betfair off-time stamping

The system SHALL capture the authoritative `marketStartTime` epoch from each Betfair market, convert it to SAST `HH:MM` as `offTime`, parse the meeting date from the event name as `eventDate` (ISO), and attach `bf_off_time`/`bf_event_date` to the snapshot event additively (never overwriting existing stamps) via a course+raceNumber fallback match when display times disagree.

#### Scenario: Exact time preserved despite placeholder
- **WHEN** Betway shows `12:00` but Betfair carries `14:05` for the same course and race number
- **THEN** the snapshot event gains `bf_off_time: 14:05` and keeps `t: 12:00`

### Requirement: Date-matched settlement gate

Settlement SHALL trust a `bf_off_time` only when its `bf_event_date` equals the bet's date; otherwise it SHALL fall back to the scan-file time. All gate datetimes SHALL be SAST-aware.

#### Scenario: Cross-edition mismatch ignored
- **WHEN** a bet from 2026-09-10 matches a market stamped for 2026-09-11
- **THEN** the gate ignores the stamp and uses the scan time for the bet's own date
