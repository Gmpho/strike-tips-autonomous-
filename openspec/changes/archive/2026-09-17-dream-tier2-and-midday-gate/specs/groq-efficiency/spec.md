## ADDED Requirements

### Requirement: Midday betting gate

The continuous (15-min) scanner SHALL skip any race already holding a same-day PENDING ticket and SHALL require edge ≥ 8.0% (above the morning 5.5% bar) before placing. Morning scan remains the discovery path; midday only upgrades.

#### Scenario: Race already backed
- **WHEN** the morning scan holds a PENDING ticket for Vaal R4
- **THEN** midday value bets on Vaal R4 place nothing, regardless of edge

#### Scenario: Higher midday bar
- **WHEN** a midday value bet shows 6.5% edge on an open race
- **THEN** it is skipped (morning bar 5.5% does not apply intraday)
