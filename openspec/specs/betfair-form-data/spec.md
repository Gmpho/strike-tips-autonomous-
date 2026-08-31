# betfair-form-data Specification

## Purpose
Defines how Betfair SA form data — per-runner **wearing gear** (hood, tongue strap, blinkers, etc.) and **days since last run** — is extracted from betfairsa.co.za, normalized, matched onto market-snapshot runners, and displayed on the HUD dashboard, with graceful degradation when Betfair is unavailable.

## Requirements

### Requirement: Betfair form data extraction

The system SHALL fetch, for every upcoming SA race published on betfairsa.co.za, the per-runner wearing gear description and the days since the horse's last run. The parser SHALL normalize gear text to the canonical token set (`Hood`, `Blinkers`, `Tongue strap`, `Visor`, `Eye shade`, `Cheek pieces`, `Cross noseband`, `Rear looker`) joined by `·`, and SHALL express days since last run as a non-negative integer. The parser SHALL return the minimal shape `{events: {eid: {runners: [{name, gear, daysSinceRun}]}}}` and SHALL NOT duplicate odds or any other Betway-owned field.

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

The system SHALL merge Betfair form data onto market-snapshot runners by matching horse names in three steps: exact match after whitespace/case normalization; then fuzzy match with `difflib.get_close_matches` at a 0.6 similarity cutoff (the same pattern as `_validate_value_bets`); then no match. A runner with no match SHALL be skipped silently — the system MUST NOT guess an attachment, because wrong-horse gear data is worse than absent data. Matched runners gain optional `gear` and `daysSinceRun` keys on the existing snapshot runner object; all other snapshot fields are untouched.

#### Scenario: Exact match attaches data

- **WHEN** Betway lists `"Night Fever"` and Betfair lists `"Night Fever"` for the same track and race
- **THEN** the snapshot runner gains Betfair's `gear` and `daysSinceRun`

#### Scenario: Fuzzy match attaches data

- **WHEN** Betway lists `"Night Fever"` and Betfair lists `"Night  Fever (IRE)"` with similarity at or above 0.6
- **THEN** the snapshot runner gains Betfair's `gear` and `daysSinceRun`

#### Scenario: No match skips silently

- **WHEN** a Betway runner matches no Betfair runner at or above the 0.6 cutoff
- **THEN** the runner keeps its existing fields with no `gear` or `daysSinceRun` key and no error is raised

### Requirement: Graceful degradation with healing observability

The system SHALL treat Betfair SA as an optional source: when the fetch, parse, or merge fails or returns empty data, the market snapshot SHALL be unaffected and the monitor cycle SHALL continue. Every Betfair failure, skip, and selector rotation SHALL be logged via `_write_healing_event()` to the shared healing log so the HUD Healing view reports Betfair health alongside Betway/ATR. If Betfair SA requires HTML scraping rather than a JSON API, the parser SHALL use the shared `SelfHealingParser` selector rotation rather than a new healing mechanism.

#### Scenario: Betfair unreachable

- **WHEN** the Betfair fetch raises or times out during a monitor cycle
- **THEN** the snapshot is published unchanged (no `gear`/`daysSinceRun` keys added) and a healing event records the failure

#### Scenario: Betfair returns empty or malformed data

- **WHEN** the Betfair response contains no parseable events
- **THEN** the merge is skipped and a healing event records the skip

#### Scenario: Partial coverage is acceptable

- **WHEN** Betfair covers only some races in the snapshot
- **THEN** covered runners gain the fields and uncovered runners are untouched in the same published snapshot

### Requirement: HUD display of gear and days since last run

The HUD SHALL render `gear` as a compact badge per runner on the RaceCard and SHALL render `daysSinceRun` as a sortable **Days** column. Absent fields SHALL render as nothing (no placeholder spinner, no "0"). The HUD SHALL NOT introduce a new data fetch — both fields arrive on the existing snapshot payload.

#### Scenario: Enriched runner rendered

- **WHEN** a snapshot runner has `gear: "Hood · Blinkers"` and `daysSinceRun: 14`
- **THEN** the RaceCard row shows the gear badge `"Hood · Blinkers"` and the Days column shows `14`, and the Days column is sortable

#### Scenario: Un-enriched runner rendered cleanly

- **WHEN** a snapshot runner has no `gear` or `daysSinceRun`
- **THEN** the gear badge and Days cell render empty with no error and no placeholder noise
