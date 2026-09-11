## ADDED Requirements

### Requirement: Off-time gate

The system SHALL NOT settle a bet before its race's scheduled off-time plus `OFF_TIME_GRACE_MINUTES` (15). Off-time is resolved as the Betfair-stamped `bf_off_time` (only when its `bf_event_date` matches the bet date) else the daily-scan `race_time` for the bet's own date; all comparisons are SAST-aware. Unknown off-time leaves the bet to evidence-based settlement.

#### Scenario: Pre-race bet stays pending
- **WHEN** a bet's off-time is in the future
- **THEN** no lookup runs and the bet stays PENDING

### Requirement: Generic winner stoplist

Winner extraction SHALL reject single-word generic captures (e.g. "choice", "favourite", "pick") via a stoplist; a loose multi-word capture containing a stoplist word is also rejected, leaving the bet PENDING instead of fabricating a LOST.

#### Scenario: Generic word rejected
- **WHEN** result text yields "1st choice"
- **THEN** no winner is extracted and the bet stays PENDING

### Requirement: Phantom void path

A previously settled LOST MAY be voided back to PENDING with precise money reversal per ledger/model (paper vs real, single vs exotic), restoring both `bankroll_state.json` and `bet_history.json`.

#### Scenario: Void restores stake
- **WHEN** a phantom LOST single is voided
- **THEN** its stake is credited back to the originating ledger and it becomes PENDING

## MODIFIED Requirements

### Requirement: Max-age deferral

The system SHALL defer (skip, leave PENDING, log for review) open bets older than `MAX_SETTLE_AGE_DAYS` (default 3), SHALL process boundary-age bets, and SHALL fail open on unparseable dates. Deferred bets SHALL appear in the aged-backlog section and SHALL be excluded from exposure.

#### Scenario: Nine-day-old bet deferred
- **WHEN** a 9-day-old open bet is scanned
- **THEN** no lookup runs, it stays PENDING, and a deferred log line names it
