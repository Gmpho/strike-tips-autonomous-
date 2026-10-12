# Capability: alert-digest-v2

## Purpose

Every Telegram odds alert answers what race, what move, and what to do —
never a naked tip.

## ADDED Requirements

### Requirement: Race context on every alert

An alert SHALL carry course, race number, off-time, and minutes-to-off.

#### Scenario: Worcester mover
- **WHEN** Sonyourastar steams at Worcester
- **THEN** the alert reads Worcester R7 with off-time, not just a course

### Requirement: Odds journey open to latest

A repeated mover SHALL render one line showing open odds (+time) to
latest odds (+time), with STEAMER/DRIFTER direction.

#### Scenario: Spong Hill pinged three times
- **WHEN** the digest contains 11.0, 9.0, and 9.5 alerts for one horse
- **THEN** they collapse to a single trail line

### Requirement: Action framing, never naked tips

A row SHALL carry an edge marker when the horse is a rated value pick,
otherwise an explicit watch-only tag; the digest header SHALL state
market movers, not tips.

#### Scenario: Non-value steamer
- **WHEN** a horse steams with no rated edge
- **THEN** the row says watch-only, never implying a selection

### Requirement: Movers only, short lines

The digest SHALL contain only horses whose price moved, one featured
biggest-mover card excepted; rows stay two lines max.

#### Scenario: Quiet half hour
- **WHEN** only four horses moved
- **THEN** the digest sends four rows, never padded with market leaders
