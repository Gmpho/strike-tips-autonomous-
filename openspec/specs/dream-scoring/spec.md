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
