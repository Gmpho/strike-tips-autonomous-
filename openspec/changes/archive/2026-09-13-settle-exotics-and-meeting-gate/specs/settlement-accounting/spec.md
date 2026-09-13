## ADDED Requirements

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
