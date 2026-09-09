# settings-ledger-consistency Specification

## Purpose
Defines the contract that persisted settings survive a save→reload cycle
unchanged, that the HUD always shows which money ledger is active, and that
every view needing bet history actually loads it.

## Requirements

### Requirement: Settings round-trip integrity

`GET /config` SHALL return the saved values for Starting Balance, Max Stake
%, Daily Stop %, and Min Edge (overlaying saved flat keys onto the bankroll
block) so a save followed by reload renders identical values.

#### Scenario: Saved base survives reload
- **WHEN** Starting Balance 3800 is saved and the page reloads
- **THEN** the form shows 3800, not the 1000 default

#### Scenario: Edited value persists both ways
- **WHEN** Min Edge is changed 5→6, saved, reloaded, reverted to 5, saved
- **THEN** the backend stores 6 then 5, and each reload matches

### Requirement: Paper-aware base reset

`POST /config` with `startingBalance` SHALL, in paper mode, reset the paper
bank and refill target — but ONLY when the value differs from the saved one,
so unrelated saves never wipe the bank as a side effect. Real-ledger
behavior (reset only pre-P&L) is unchanged.

#### Scenario: Toggle-save preserves bank
- **WHEN** only a Telegram toggle changes and Starting Balance is unchanged
- **THEN** paper and real balances are untouched

### Requirement: Ledger identity in HUD state

The bankroll store update SHALL preserve `paperMode`, `paperBalance`, and
`realBalance` on every poll; the header SHALL badge Capital as PAPER or LIVE
with a tooltip naming the active ledger; the Bankroll view SHALL show the
active bank plus the untouched other ledger.

#### Scenario: Paper polling keeps identity
- **WHEN** five-second polls run for a minute in paper mode
- **THEN** the badge stays PAPER and the real-funds line remains visible

### Requirement: Settings load resilience

The settings form SHALL retry the config fetch with backoff (up to 4
attempts) instead of sticking at defaults after a single cold-start failure.

#### Scenario: Cold container first load
- **WHEN** the first config fetch fails while Modal wakes
- **THEN** a retry populates the form within ~20s instead of showing defaults

### Requirement: Ledger hydration coverage

`betHistory` SHALL hydrate on every view that renders from it (bankroll,
analytics, exotics), so the Exotics Settle Ledger lists recorded tickets.

#### Scenario: Direct exotics visit
- **WHEN** the exotics view loads with no prior bankroll/analytics visit
- **THEN** the Settle Ledger still lists all recorded exotic tickets
