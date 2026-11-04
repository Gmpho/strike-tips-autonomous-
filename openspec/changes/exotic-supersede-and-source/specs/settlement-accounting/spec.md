## MODIFIED Requirements

### Requirement: Duplicate cancellation and expiry

Same track/date/pool recordings SHALL keep the earliest ticket and cancel the
rest (stake refund, VOID status) — EXCEPT that a later scan MAY supersede an
earlier ticket for the same pool when all of the following hold: the earlier
ticket is still PENDING, its paper/real mode matches, and none of its legs has
started. A superseded ticket SHALL be set VOID (removing it from the duplicate
key set) with a note recording the replacement source, and its stake SHALL be
refunded. Settled (WON/LOST) tickets SHALL never be superseded. Where the off
time of any leg is in the past or cannot be read, supersede SHALL be refused.
PENDING bets older than the max settle age SHALL expire (EXPIRED, no money
moves) instead of piling up.

#### Scenario: Value scan replaces the daily scan's pick
- **WHEN** the 09:30 value scan records a pool the 05:00 daily scan already
  placed, the daily ticket is still PENDING, and no leg has started
- **THEN** the daily ticket is set VOID and refunded, and the value ticket is
  recorded as the live ticket for that pool

#### Scenario: Quadruple-recorded bipot
- **WHEN** four identical Bipot tickets exist for one day
- **THEN** one survives to settle and three cancel with refunds

#### Scenario: Settled ticket is never replaced
- **WHEN** a later scan requests supersede for a ticket already WON or LOST
- **THEN** no replacement is recorded and the settled ticket is unchanged

#### Scenario: Meeting already started
- **WHEN** any leg of the existing ticket has an off time in the past, or the
  off time cannot be read
- **THEN** supersede is refused and the existing ticket is kept

#### Scenario: Different paper/real mode
- **WHEN** a supersede request targets an existing ticket in the other
  paper/real mode
- **THEN** the request is refused (first-wins) and no money moves

## ADDED Requirements

### Requirement: Partial-feed leg safety

An exotic leg SHALL be declared dead only when the results data carries every
placing the pool requires. When the confirmed placings are incomplete, the leg
SHALL stay unknown and the ticket SHALL stay PENDING, never LOST. A listed
runner with no published placing SHALL be treated as missing data rather than
a loss, for multi-leg pools and single-race pools (Exacta/Trifecta/Quartet)
alike.

#### Scenario: Winner published, placings not yet
- **WHEN** a place-pool leg's feed lists a confirmed 1st but no 2nd or 3rd,
  and the ticket's candidates matched rows by name
- **THEN** the leg stays unknown and the ticket stays PENDING

#### Scenario: Complete feed still settles
- **WHEN** every placing the pool requires is confirmed and no candidate meets
  it
- **THEN** the leg is dead and the ticket settles LOST

#### Scenario: Blank single-race banker
- **WHEN** an Exacta banker is listed in the results with no placing
- **THEN** the leg stays unknown and the ticket stays PENDING

### Requirement: Forensic settlement notes

A LOST exotic verdict SHALL record, in the ticket notes, which leg races died
and the confirmed placing of each candidate in those legs.

#### Scenario: Dead leg evidence
- **WHEN** an exotic ticket settles LOST
- **THEN** the notes name the dead leg race numbers and each candidate's
  confirmed placing

### Requirement: Scan provenance on exotic tickets

Each exotic ticket SHALL record the scan that placed it as `source` in its
notes JSON, so daily-scan and value-scan picks are distinguishable in the
ledger.

#### Scenario: Source recorded
- **WHEN** an exotic ticket is recorded by the daily or the value scan
- **THEN** its notes JSON carries `source` = `daily` or `value`
