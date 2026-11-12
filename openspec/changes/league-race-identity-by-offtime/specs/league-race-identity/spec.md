# Capability: league-race-identity

## Purpose
Define how a league pick is matched to the race it was placed in, so that a
pick can never be settled against a different race than the one it names.

## ADDED Requirements

### Requirement: A race is identified by its off time

The system SHALL resolve a pick's race against result evidence by the pick's
**off time** first — converted to UTC — and SHALL use the stored race number
only when the off-time resolution finds no race that contains the picked
horse. The off time is the one identifier every feed agrees on; the race
number is not portable (Nov-2026: Betway numbered the Horseshoe Indianapolis
meeting differently from ATR, so the pick's stored number pointed at a
different race).

#### Scenario: Stored race number names the wrong race
- **WHEN** a pick's stored race_number resolves to a race that does not
  contain the picked horse, and ATR holds a race at the pick's off time whose
  card does contain the horse
- **THEN** the pick is settled against the off-time race

#### Scenario: Off time resolves nothing
- **WHEN** no result evidence exists for the pick's off time
- **THEN** the race-number lookup is used, exactly as before

### Requirement: A pick is never settled against a race it was not placed in

The system SHALL NOT settle a pick against a card whose race identity is in
dispute. When the race proven by the pick's own off time and the race named by
the stored race number disagree, and neither card places the picked horse,
the pick SHALL stay PENDING.

#### Scenario: Horse on neither card
- **WHEN** the picked horse is on neither the off-time card nor the card for
  the stored race number, and the two cards disagree about the race
- **THEN** the pick stays PENDING — no verdict is taken from either card

### Requirement: Mis-numbered picks are repaired

The system SHALL correct a pick's stored `race_number` when result evidence
for the pick's **own off time** proves a different race number for that
meeting AND the picked horse is on that race. The original value SHALL be
preserved on the pick for audit.

#### Scenario: Feed number disagrees with ATR
- **WHEN** a pick stored race 3 for a race ATR numbers 1, and the horse ATR
  lists in R1 is the picked horse
- **THEN** the stored race_number becomes 1 and the original is kept in
  `race_number_corrected`

#### Scenario: No proof, no change
- **WHEN** the picked horse is not on the race ATR holds for the pick's off
  time
- **THEN** the stored race_number is left untouched and the pick stays
  PENDING

### Requirement: Race time keys are timezone explicit

Confirmed cards SHALL carry the race's off time in UTC (`off_time_utc`) so a
card can be matched by instant regardless of the source's local clock. A card
without a resolvable UTC time SHALL fall back to the race-number path.

#### Scenario: Raceform card written in local time
- **WHEN** a Raceform card records `off_time` "12:15" for a South African
  meeting
- **THEN** the card also carries `off_time_utc` "10:15"

#### Scenario: Offtrackbetting card already in UTC
- **WHEN** an Offtrackbetting card records `off_time` "18:30"
- **THEN** the card carries `off_time_utc` "18:30"

### Requirement: A repair never rewrites a settled verdict

The repair pass SHALL NOT renumber a pick that was settled with a finishing
position, and SHALL never downgrade a settled verdict — the re-score pass
remains the only path that upgrades one.

#### Scenario: Pick settled with a position
- **WHEN** a pick already carries `finish_position`
- **THEN** the repair pass leaves its race_number alone
