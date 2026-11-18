# Capability: exotic-ticket-identity

## Purpose

One ticket per (date, track, pool family, legs) per day, with no churn when a
scan re-offers the same selections.

## ADDED Requirements

### Requirement: Identical selections are not a supersede

`record_exotic_bet` SHALL return the existing PENDING ticket when the incoming
ticket's selections are identical to it, instead of voiding it and recording a
replacement.

#### Scenario: Same scan re-records the same pool

- **WHEN** a call with `supersede=True` offers the same legs and the same
  bankers/savers as the live PENDING ticket
- **THEN** the existing ticket is returned unchanged
- **AND** exactly one PENDING row exists and no VOID row is created
- **AND** the stake is neither refunded nor charged twice

#### Scenario: Fresher selections supersede

- **WHEN** a call with `supersede=True` offers different bankers or savers
- **THEN** the prior PENDING ticket is voided and refunded, and a new ticket is
  recorded (unchanged behaviour)

#### Scenario: Settled ticket protection

- **WHEN** the existing ticket is WON or LOST
- **THEN** it is never modified, superseded, or re-recorded
