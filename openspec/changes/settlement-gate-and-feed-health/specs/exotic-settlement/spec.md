# Capability: exotic-settlement

## Purpose

Settle exotic pool tickets only on dated proof, and never spend a result-source
lookup on a ticket whose races have not run.

## ADDED Requirements

### Requirement: Off-time gate precedes result acquisition

`_settle_exotic_ticket` SHALL resolve the final leg's off-time and return
`before_off_time` before it acquires any result source (monitor cache,
Raceform, or ATR `/results`).

#### Scenario: Ticket whose pool has not finished

- **WHEN** a ticket's final leg is scheduled more than `OFF_TIME_GRACE_MINUTES`
  in the future
- **THEN** the ticket stays PENDING with reason `before_off_time`
- **AND** no result-source fetch is attempted for it

#### Scenario: Unknown off-time

- **WHEN** the off-time cannot be resolved for the ticket's own day
- **THEN** the ticket proceeds to evidence, and only confirmed, dated results
  can settle or void it
