# Capability: exotics-textbook

## Purpose

TAB form stays the data source of truth; OKF carries the doctrine for
constructing and selecting exotic tickets, and the builder enforces it.

## ADDED Requirements

### Requirement: Textbook shapes tickets, TAB decides facts

Ticket construction SHALL follow the OKF doctrine (widen-the-murk,
flagged auto-qualify, suitability gate) while pool facts (legs, minimums,
deadlines) SHALL come from TAB data, never the textbook.

#### Scenario: Murkiest leg widened
- **WHEN** a jackpot blueprint has legs of differing uncertainty and a
  widening budget of 1
- **THEN** exactly the murkiest leg gains a 4th horse and is marked widened

#### Scenario: Flagged winner never left off
- **WHEN** analysis flags a horse in a ticket leg
- **THEN** the ticket contains that horse (displacing the weakest saver)

### Requirement: Single-race pools are gated by suitability

Quartet SHALL require 12+ runner fields, Trifecta 8+, Exacta a duel —
never sprayed on every race.

#### Scenario: Small field gets Exacta only
- **WHEN** a race has 6 runners
- **THEN** suitability returns Exacta and no Trifecta or Quartet
