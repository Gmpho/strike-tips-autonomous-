# dream-scoring Specification

## Purpose
Prove dreams add skill: score every scenario prediction against reality with Brier math, per family.

## Requirements

### Requirement: Prediction ledger

Every generated dream SHALL append one line to `dream_ledger.jsonl`: dream id, date, track, race, scenario family (going/wind/scratch/sentiment/other), favorite name + odds, implied probability, predicted probability (implied × (1+shift), clamped 0.01–0.99).

#### Scenario: Dream recorded
- **WHEN** a dream simulates Turffontein R5 with a +0.05 shift on a 4.0 favorite
- **THEN** the ledger holds predicted_p = 0.2625 with family and date

### Requirement: Settled winners log

Every confirmed single-winner settlement SHALL append `{date, track, race, winner}` to `settled_winners.jsonl` (best-effort, never blocks settlement).

#### Scenario: Winner captured
- **WHEN** a bet settles with confirmed winner "Pressonregardless"
- **THEN** the log holds that winner for the track/race/date

### Requirement: Family calibration

A daily `calibrate_dreams()` job SHALL match ledger dreams to logged winners by (date, track, race), compute Brier score per dream vs an implied-only baseline, and persist per-family mean skill (`baseline − family`, positive = dreams help) to `dream_calibration.json`. Dreams with no matching winner are skipped, never scored.

#### Scenario: Skilled family detected
- **WHEN** going-family dreams average Brier 0.18 vs baseline 0.22
- **THEN** calibration records going skill +0.04

### Requirement: Automatic tier selection

`generate_dream` with `allow_llm=None` (default) SHALL select Tier-2 (Groq sim) when an open ticket exists for the dream's track+race, else Tier-1 (deterministic screen). Explicit True/False SHALL override.

#### Scenario: Bet race earns a sim
- **WHEN** a dream targets a race holding a PENDING ticket
- **THEN** a Groq sim runs with enriched inputs

#### Scenario: Quiet race screened free
- **WHEN** a dream targets a race with no open tickets
- **THEN** no Groq call is made (tested: Groq entry raises if touched)

### Requirement: Enriched custom dreams

User-invoked custom dreams SHALL include Betfair brief lines and enriched shift math like background dreams.

#### Scenario: /dream command
- **WHEN** a user dreams a specific track/race with a scenario
- **THEN** the prompt carries that race's Betfair briefs
