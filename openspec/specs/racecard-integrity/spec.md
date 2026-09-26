# racecard-integrity Specification

## Purpose
Guarantee every card, play, and ticket the system publishes belongs to today's actual meetings.

## Requirements

### Requirement: Future-meeting gate

The morning scan SHALL drop any track Betfair proves is not running today (course known, none of its event dates is today). Unknown courses fail open. Dropped tracks log loudly with the offending dates.

#### Scenario: Thursday card harvested Sunday
- **WHEN** TAB serves Thursday Vaal during Sunday's scan and Betfair dates Vaal 2026-09-17
- **THEN** Vaal leaves Sunday's scan with zero races and a gate log line

### Requirement: Per-track exotic attribution

Exotic plays SHALL be built once per non-empty track and stamped with that track only; first-dict-key labelling is forbidden.

#### Scenario: Multi-track scan day
- **WHEN** the scan holds Scottsville, Durbanville, and Vaal cards
- **THEN** no play carries a track it was not built from

### Requirement: Phantom-meeting guard

A play SHALL reach the board only when at least half its bankers run at its track in today's snapshot; otherwise it is dropped as a suspected phantom.

#### Scenario: Mislabeled Thursday play
- **WHEN** a "turffontein" play's bankers appear nowhere in Turffontein's snapshot runners
- **THEN** the play never reaches the board or auto-bet
