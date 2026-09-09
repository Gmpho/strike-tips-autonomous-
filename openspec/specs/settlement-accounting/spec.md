# settlement-accounting Specification

## Purpose
Defines how open bets are automatically settled from race results, how
settlement feeds the bankroll and reports, and how stale backlog is contained.
This capability turns recorded bets into settled wins/losses so the bankroll,
daily reports, analytics, and learning engine reflect reality.

## Requirements

### Requirement: ATR date labels

The system SHALL convert BetRecord ISO dates to the relative labels the ATR
results pages understand (`today` for same-day, `yesterday` otherwise) before
lookup, and SHALL never emit a raw ISO string into a results URL.

#### Scenario: Same-day bet uses today label
- **WHEN** a bet dated today is settled
- **THEN** the ATR lookup requests `/results/today`, not `/results/2026-09-04`

#### Scenario: Unparseable date fails open
- **WHEN** a bet date is missing or not ISO-parseable
- **THEN** the lookup proceeds with `yesterday` instead of raising

### Requirement: Win and loss settlement

The system SHALL settle a bet WON when the bet horse is confirmed winner
(confidence ≥ 0.55) and SHALL settle it LOST when a different winner is
confirmed for the same race (fuzzy match below 0.55). A race with no
confirmed winner SHALL leave the bet PENDING.

#### Scenario: Confirmed different winner settles loss
- **WHEN** results confirm `Other Horse (1st)` for the bet's race
- **THEN** the bet settles LOST with notes naming the confirmed winner

### Requirement: Exotic tickets excluded from single-winner settlement

The system SHALL skip bets with `confidence == EXOTIC` or `:` in the horse
field during single-winner auto-settlement, SHALL NOT call the results
lookup for them, and SHALL leave them PENDING for dividend-based settlement.

#### Scenario: Exotic open bet untouched
- **WHEN** an open `PICK6:4-5-6-7-8-9` ticket is scanned
- **THEN** no lookup runs, no settle is attempted, and it stays PENDING

### Requirement: Settled-flag honor

The system SHALL treat a `settle_bet` status dict with `settled: false` as a
failure (falling back to the governor) and SHALL NOT log, notify, or record
a settlement that did not happen.

#### Scenario: Failed brain settle falls back
- **WHEN** `brain.strike.settle_bet` returns `{"settled": False}`
- **THEN** the governor path is attempted and exactly one settle is recorded

### Requirement: Max-age deferral

The system SHALL defer (skip, leave PENDING, log for review) open bets older
than `MAX_SETTLE_AGE_DAYS` (default 3), SHALL process boundary-age bets, and
SHALL fail open on unparseable dates.

#### Scenario: Nine-day-old bet deferred
- **WHEN** a 9-day-old open bet is scanned
- **THEN** no lookup runs, it stays PENDING, and a deferred log line names it

### Requirement: Dated reports and morning recap

`generate_daily_report(report_date)` SHALL filter bets to the given ISO date
(default today) with correctly labeled sections, SHALL include an aged-backlog
section listing PENDING bets older than the max age (capped at 20 + overflow
count), and the scheduler SHALL send yesterday's recap at 07:00 SAST via
Telegram in addition to the 20:00 end-of-day report.

#### Scenario: Morning recap renders yesterday
- **WHEN** the 07:00 job runs
- **THEN** Telegram receives yesterday's settled/open lines plus the aged
  review section, titled as a morning recap

### Requirement: Bankroll history integrity

`get_bankroll_history()` SHALL return `[{t, balance}]` for the active ledger
(paper vs real), SHALL end exactly at the live balance, SHALL start at the
reconstructed opening, and SHALL floor every point at zero (paper refills
have no ledger entries and can otherwise imply a negative start).

#### Scenario: Refill drift floored
- **WHEN** lifetime settled P&L exceeds the live paper balance
- **THEN** the series starts at 0.0, never goes negative, and still ends at
  the live balance

### Requirement: Exposure excludes stale backlog

`get_open_exposure()` SHALL exclude PENDING bets older than the max settle
age by default (opt-in via `include_stale=True`), and `can_bet_today()` plus
the account-summary display SHALL use the active figure so a dead backlog
cannot permanently wall the governor.

#### Scenario: Wall lifted
- **WHEN** R2500 of 9-day-old pending stakes exist and a fresh R40 bet is sized
- **THEN** the limit check passes on the R0 active exposure
