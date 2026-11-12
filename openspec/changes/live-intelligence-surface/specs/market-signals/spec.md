## Purpose

Define how "something happened in a market" is recorded and shared, so that
every Strike Tips surface reports the same fact, from the same source, at
the same age. Today one price move is expressed four ways (a Logs alert, a
Market Movers card, a Live Ops telemetry line, a Telegram digest row) from
four different derivations, so the surfaces disagree and none of them is
attached to the user's own pick.

## ADDED Requirements

### Requirement: One canonical market event

The system SHALL record every market event as a single canonical record
carrying, at minimum: a stable id, the event timestamp, the event kind
(price move, odds drop, race start, race result, settlement), the race
identity (race id, course, race number), the runner (name and number where
known), the previous and current prices, the percentage move, a severity, the
source that produced it, and whether the event concerns the user's own
league pick. The record SHALL be the only representation of that event —
surfaces SHALL NOT derive their own version of it.

#### Scenario: One move, one record
- **WHEN** a runner's price moves from 3.5 to 2.87
- **THEN** exactly one canonical event exists for that move, and the Movers
  tab, the Live tab, the Logs audit and the Telegram digester all read that
  same record

#### Scenario: The event knows the user's pick
- **WHEN** the move concerns a runner the user holds a league pick on
- **THEN** the canonical record marks it as the user's pick

### Requirement: Price moves come from our own snapshot

The system SHALL compute price moves by diffing consecutive market snapshots
(5-minute cadence, all books) and SHALL write them to the canonical event
store as the primary source. A move SHALL be recorded only when the price
changes within the same book, the change exceeds a configured threshold, and
the change is not the opening of a market (a placeholder price becoming a
real price is not a move). The system SHALL debounce repeated moves in the
same race so one busy race cannot flood every surface.

#### Scenario: A real move is recorded
- **WHEN** a runner's price in one book moves from 11.0 to 6.5 across two
  snapshots
- **THEN** a price-move event is recorded with the previous price, the new
  price and the percentage change

#### Scenario: A market opening is not a move
- **WHEN** a runner's price changes from a placeholder to a real price
- **THEN** no move event is recorded for that change

#### Scenario: A busy race cannot flood the surfaces
- **WHEN** the same race produces many small changes inside one poll window
- **THEN** the changes are collapsed into a single event per runner and the
  per-race cooldown suppresses repeats

### Requirement: ATR's movers are a labelled fallback, never the primary

The system SHALL keep ATR's Market Movers feed only as a fallback source for
meetings the snapshot does not cover, SHALL tag every event it produces with
that source, and SHALL show the event's age wherever it is displayed. No
surface SHALL treat an ATR movers event as fresher than it is.

#### Scenario: A meeting we do not scrape still shows moves
- **WHEN** ATR's movers page reports a move for a meeting absent from our
  market snapshot
- **THEN** the event is recorded with the ATR source tag and its age

#### Scenario: The age of the source is visible
- **WHEN** a user views a movers entry
- **THEN** the entry states which source produced it and how old it is

### Requirement: Every surface reads the canonical store

The Movers tab, the Live tab, the Logs audit trail and the Telegram digester
SHALL all read the canonical event store. A surface SHALL NOT keep a private
derivation of a market event, and a change to one surface SHALL NOT require
a matching change to another to keep them consistent.

#### Scenario: Logs and the Movers tab agree
- **WHEN** the same price move appears in the Logs audit trail and on the
  Movers tab
- **THEN** both show the same prices, the same timestamp and the same source

### Requirement: Signal freshness is explicit

The system SHALL state the age of the data it displays. A surface SHALL NOT
label a race as live on data older than the poll window, and the Live tab
SHALL NOT render a live badge for a race whose last price update falls
outside that window.

#### Scenario: A stale race is not labelled live
- **WHEN** the newest price for a race is older than the poll window
- **THEN** the race is shown with its data age and without a live badge

### Requirement: In-play prices are opportunistic, never assumed

The system SHALL render the Live tab on the price data it actually has. The
ability to show price changes during a running race depends on holding a
push connection to the bookmaker's racing feed, and that capability SHALL be
established separately before the Live tab claims in-play prices. Absence of
that capability SHALL NOT block the Live tab; the tab SHALL show pre-race
movement and the result instead.

#### Scenario: No push connection available
- **WHEN** no push connection is established and a race is running
- **THEN** the Live tab shows the last known prices, their age, and the
  result once it lands — and does not describe itself as showing in-play
  prices
