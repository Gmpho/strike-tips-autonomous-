## ADDED Requirements

### Requirement: Exact off-time, meeting date, and distance

The parser SHALL capture the authoritative `marketStartTime` as SAST `offTime` and `raceNumber` from the market name, SHALL parse the meeting date from the event name (`"11 Sep"` → ISO), and SHALL parse distance from market names (`1200m`, `6f`, `1m1f`) into `distanceM` metres. `eventDate`/`distanceM`/`offTime` travel with the event as `eventDate`/`distanceM`/`offTime`; absent values are omitted, never fabricated.

#### Scenario: Exact time over UTC label
- **WHEN** a market carries `marketStartTime` for `12:15 SAST` and a `timeLabel` of `10:15`
- **THEN** the event's `offTime` is `12:15`

## MODIFIED Requirements

### Requirement: Betfair form data extraction

The system SHALL fetch, for every upcoming race published on betfairsa.co.za (all regions when `_COUNTRY_FILTER=None`, SA-only when set to `{"ZA"}`), the per-runner enriched fields: wearing gear (`gear`), days since last run (`daysSinceRun`), runner comments, jockey claim, official rating, pedigree, owner, verdict, trainer, age, weight, and form, plus meeting-level `offTime`, `eventDate`, and `distanceM`. The parser SHALL normalize gear text to the canonical token set (`Hood`, `Blinkers`, `Tongue strap`, `Visor`, `Eye shade`, `Cheek pieces`, `Cross noseband`, `Rear looker`) joined by `·`, SHALL express days since last run as a non-negative integer and official_rating/age as integers, and SHALL clean course names (`"Fairview (RSA) 11 Sep"` → `"Fairview"`). The parser SHALL return the shape `{events: {eid: {course, t: offTime or "00:00", raceName, raceNumber?, offTime?, eventDate?, distanceM?, runners: [{name, gear, daysSinceRun, ...}]}}}` with absent fields omitted, and SHALL NOT duplicate odds or any other Betway-owned field.

#### Scenario: Gear text normalized
- **WHEN** Betfair reports gear as `"Hood/Tongue Strap/BLINKERS"`
- **THEN** the parsed value is `"Hood · Tongue strap · Blinkers"`

#### Scenario: Days since run parsed as integer
- **WHEN** Betfair reports last-run info equivalent to 14 days ago
- **THEN** `daysSinceRun` is the integer `14`

#### Scenario: No gear declared
- **WHEN** a runner has no gear declared on Betfair
- **THEN** the runner's `gear` value is absent (not an empty string) and `daysSinceRun` may still be present

### Requirement: Snapshot merge with fuzzy horse matching

The system SHALL merge Betfair form data onto market-snapshot runners by matching horse names in three steps: exact match after whitespace/case normalization; then fuzzy match with `difflib.get_close_matches` at a 0.6 similarity cutoff (the same pattern as `_validate_value_bets`); then no match. If display times disagree, a fallback match on `(course, raceNumber)` SHALL still merge. A runner with no match SHALL be skipped silently — the system MUST NOT guess an attachment, because wrong-horse data is worse than absent data. Matched runners gain optional enriched keys (`gear`, `daysSinceRun`, `runner_comments`, `jockey_claim`, `official_rating`, `pedigree`, `owner`, `verdict`, `trainer`, `age`, `weight`, `form`) on the existing snapshot runner object; the event gains `bf_off_time`, `bf_event_date`, and `distance_m` additively and never overwrites existing stamps. All other snapshot fields are untouched and existing keys are never overwritten (additive only, one-to-one matching).

#### Scenario: Exact match attaches data
- **WHEN** Betway lists `"Night Fever"` and Betfair lists `"Night Fever"` for the same track and race
- **THEN** the snapshot runner gains Betfair's `gear` and `daysSinceRun`

#### Scenario: Fuzzy match attaches data
- **WHEN** Betway lists `"Night Fever"` and Betfair lists `"Night  Fever (IRE)"` with similarity at or above 0.6
- **THEN** the snapshot runner gains Betfair's `gear` and `daysSinceRun`

#### Scenario: No match skips silently
- **WHEN** a Betway runner matches no Betfair runner at or above the 0.6 cutoff
- **THEN** the runner keeps its existing fields with no `gear` or `daysSinceRun` key and no error is raised
