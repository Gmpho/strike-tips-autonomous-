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

The system SHALL defer (skip, leave PENDING, log for review) open bets older than `MAX_SETTLE_AGE_DAYS` (default 3), SHALL process boundary-age bets, and SHALL fail open on unparseable dates. Deferred bets SHALL appear in the aged-backlog section and SHALL be excluded from exposure.

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

### Requirement: Off-time gate

The system SHALL NOT settle a bet before its race's scheduled off-time plus `OFF_TIME_GRACE_MINUTES` (15). Off-time is resolved as the Betfair-stamped `bf_off_time` (only when its `bf_event_date` matches the bet date) else the daily-scan `race_time` for the bet's own date; all comparisons are SAST-aware. Unknown off-time leaves the bet to evidence-based settlement.

#### Scenario: Pre-race bet stays pending
- **WHEN** a bet's off-time is in the future
- **THEN** no lookup runs and the bet stays PENDING

### Requirement: Generic winner stoplist

Winner extraction SHALL reject single-word generic captures (e.g. "choice", "favourite", "pick") via a stoplist; a loose multi-word capture containing a stoplist word is also rejected, leaving the bet PENDING instead of fabricating a LOST.

#### Scenario: Generic word rejected
- **WHEN** result text yields "1st choice"
- **THEN** no winner is extracted and the bet stays PENDING

### Requirement: Phantom void path

A previously settled LOST MAY be voided back to PENDING with precise money reversal per ledger/model (paper vs real, single vs exotic), restoring both `bankroll_state.json` and `bet_history.json`.

#### Scenario: Void restores stake
- **WHEN** a phantom LOST single is voided
- **THEN** its stake is credited back to the originating ledger and it becomes PENDING

### Requirement: Exotic leg settlement

Exotic tickets SHALL be evaluated leg-by-leg against ATR placed results using named banker/saver candidates: win pools (Pick 6/3, Jackpot) require 1st; Bipot requires 1st/2nd; Place Accumulator requires 1st/2nd/3rd. A leg passes when banker or saver meets the requirement (fuzzy ≥ 0.55).

#### Scenario: Dead jackpot leg settles LOST
- **WHEN** no candidate in a Jackpot leg won its confirmed race
- **THEN** the ticket settles LOST for a R0 return with no dividend needed

### Requirement: Dividend-gated exotic wins

An all-legs-passing ticket SHALL settle WON only with a scraped tote dividend (return = dividend-per-R1 × stake); without a dividend it SHALL stay PENDING marked awaiting-dividend, never on the placement estimate.

#### Scenario: Full house without dividend
- **WHEN** every leg passes but no tote dividend is found
- **THEN** no settle occurs and the ticket stays PENDING

### Requirement: ATR verification window

Exotic auto-settlement SHALL apply only to tickets aged ≤ 1 day (ATR serves today/yesterday only); older tickets stay PENDING for the expiry sweep.

#### Scenario: Two-day-old ticket untouched
- **WHEN** a 2-day-old ticket has losing legs against the wrong day's page
- **THEN** no settle occurs

### Requirement: Duplicate cancellation and expiry

Same track/date/ticket recordings SHALL keep the earliest and cancel the rest (stake refund, VOID status); PENDING bets older than the max settle age SHALL expire (EXPIRED, no money moves) instead of piling up.

#### Scenario: Quadruple-recorded bipot
- **WHEN** four identical Bipot tickets exist for one day
- **THEN** one survives to settle and three cancel with refunds

### Requirement: Void and cancel admin endpoint

`POST /api/betting/void` with `{bet_id, action: void|cancel, reason}` SHALL reverse wrongful settles (void) or scrap phantom PENDINGs with refund (cancel). Keyed by the existing auth middleware; no spec change there.

#### Scenario: Phantom ticket cancelled
- **WHEN** an admin cancels a PENDING phantom with reason
- **THEN** the stake is refunded to its ledger and status becomes VOID
