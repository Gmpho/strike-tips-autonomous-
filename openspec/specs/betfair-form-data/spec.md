# betfair-form-data Specification

## Purpose
Defines how Betfair form data — per-runner **wearing gear**, **days since last run**, and enriched fields (**runner_comments**, **jockey_claim**, **official_rating**, **pedigree**, **owner**, **verdict**, **trainer**, **age**, **weight**, **form**) — is extracted from betfairsa.co.za (and optionally other regions when `_COUNTRY_FILTER=None`), normalized, matched onto market-snapshot runners, and displayed on the HUD dashboard, with graceful degradation when Betfair is unavailable.

## Requirements

### Requirement: Betfair form data extraction

The system SHALL fetch, for every upcoming race published on betfairsa.co.za (all regions when `_COUNTRY_FILTER=None`, SA-only when set to `{"ZA"}`), the per-runner enriched fields: wearing gear (`gear`), days since last run (`daysSinceRun`), runner comments, jockey claim, official rating, pedigree, owner, verdict, trainer, age, weight, and form. The parser SHALL normalize gear text to the canonical token set (`Hood`, `Blinkers`, `Tongue strap`, `Visor`, `Eye shade`, `Cheek pieces`, `Cross noseband`, `Rear looker`) joined by `·`, and SHALL express days since last run as a non-negative integer and official_rating/age as integers. The parser SHALL return the shape `{events: {eid: {runners: [{name, gear, daysSinceRun, runner_comments, jockey_claim, official_rating, pedigree, owner, verdict, trainer, age, weight, form}]}}}` with absent fields omitted, and SHALL NOT duplicate odds or any other Betway-owned field.

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

The system SHALL merge Betfair form data onto market-snapshot runners by matching horse names in three steps: exact match after whitespace/case normalization; then fuzzy match with `difflib.get_close_matches` at a 0.6 similarity cutoff (the same pattern as `_validate_value_bets`); then no match. A runner with no match SHALL be skipped silently — the system MUST NOT guess an attachment, because wrong-horse data is worse than absent data. Matched runners gain optional enriched keys (`gear`, `daysSinceRun`, `runner_comments`, `jockey_claim`, `official_rating`, `pedigree`, `owner`, `verdict`, `trainer`, `age`, `weight`, `form`) on the existing snapshot runner object; all other snapshot fields are untouched and existing keys are never overwritten (additive only, one-to-one matching).

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

### Requirement: HUD display of enriched Betfair fields

The HUD SHALL render `gear` as a compact badge per runner on the RaceCard and SHALL render `daysSinceRun` as a sortable **Days** column, and SHALL render enriched fields (`runner_comments`, `verdict`, `official_rating`, `jockey_claim`, `pedigree`, `owner`) in the expanded runner detail row. Absent fields SHALL render as nothing (no placeholder spinner, no "0"). The HUD SHALL NOT introduce a new data fetch — all fields arrive on the existing snapshot payload. The expanded row SHALL be expandable when any enriched field or insight is present.

#### Scenario: Enriched runner rendered

- **WHEN** a snapshot runner has `gear: "Hood · Blinkers"` and `daysSinceRun: 14`
- **THEN** the RaceCard row shows the gear badge `"Hood · Blinkers"` and the Days column shows `14`, and the Days column is sortable

#### Scenario: Un-enriched runner rendered cleanly

- **WHEN** a snapshot runner has no `gear` or `daysSinceRun`
- **THEN** the gear badge and Days cell render empty with no error and no placeholder noise

#### Scenario: Expanded enriched detail

- **WHEN** a runner has `runner_comments: "Needs further"`, `official_rating: 95`, and `verdict: "Leading contender"`
- **THEN** expanding the row shows those fields in the detail grid and the row is expandable even without a timeform/swarm insight

#### Scenario: All-regions ingestion

- **WHEN** `_COUNTRY_FILTER=None` and Betfair lists UK and SA groups
- **THEN** both regions' markets are fetched and merged (not just `countryCode == "ZA"`)
