# Capability: atr-course-context

## Purpose

Every ATR card states WHERE it runs. No user cross-references elsewhere.

## ADDED Requirements

### Requirement: Meeting context on every entry

Movers and predictions SHALL carry course (and region/time when available)
from meeting headers, cell parse, or snapshot cross-ref — in that priority.

#### Scenario: Grouped page
- **WHEN** ATR groups tables under "Newcastle" headers
- **THEN** all rows in the group carry course Newcastle, region UK

#### Scenario: Backfill
- **WHEN** ATR omits course but the snapshot holds the horse
- **THEN** the written snapshot fills course/time without overwriting ATR values

### Requirement: Defunct tracks never resolve live

Flamingo/Kimberley codes SHALL resolve to a defunct marker, never a live track.

#### Scenario: Kimberley code
- **WHEN** a code maps to the closed Kimberley circuit
- **THEN** track reads "Flamingo Park (closed 2020)" with region defunct
