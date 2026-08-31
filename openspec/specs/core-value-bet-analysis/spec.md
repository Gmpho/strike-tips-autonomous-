# core-value-bet-analysis Specification

## Purpose
Defines how Strike Tips identifies value bets in South African horse racing and sizes stakes under hard bankroll discipline: probability-edge math, anti-hallucination validation, half-Kelly stake sizing scaled by the Dream Stress Index (DSI), hard circuit breakers, and the bet lifecycle.

## Requirements

### Requirement: Probability-edge value detection

The system SHALL judge a runner as a value-bet candidate by comparing the model's estimated win probability against the runner's implied probability derived from its decimal odds, computed as `edge = (estimated_probability - 1/decimal_odds) * 100`. A runner SHALL be proposed as a value bet only when the resulting edge is at least 5.0 percentage points, and the decimal odds are above 1.01.

#### Scenario: Above threshold

- **WHEN** a horse's edge is at least 5.0% and its decimal odds are above 1.01
- **THEN** the horse is proposed as a value bet

#### Scenario: Below threshold

- **WHEN** a horse's edge is below 5.0%
- **THEN** the horse is not proposed as a value bet and any eligible stake resolves to 0

### Requirement: Auto-bet odds resolution never assumes a price

The system SHALL resolve a bettable decimal odd for a value bet from the offered price already present on the bet (e.g. `odds_decimal`, `offered_odds`, `bookmaker_odds`, `odds`). The resolution SHALL return no bet when the price is missing, non-numeric, or less than or equal to 1.01. The system MUST NOT invent or default to a plausible assumed price, because an assumed odd corrupts stake sizing, settlement math, and learning statistics.

#### Scenario: Valid price present

- **WHEN** an offered price exists, is numeric, and is greater than 1.01
- **THEN** that decimal odd is resolved for the bet

#### Scenario: Missing or invalid price

- **WHEN** the offered price is absent, non-numeric, or at most 1.01
- **THEN** resolution yields no bet and no auto-bet is placed

### Requirement: Hallucination-safe value validation

The system SHALL ensure every value bet for a race references a real runner on that same race card. A candidate name SHALL be accepted on exact match and SHALL be normalized to the real runner's name on a fuzzy match at or above a 0.6 similarity cutoff. A candidate that matches no real runner SHALL be discarded as a hallucination and SHALL NOT be notified.

#### Scenario: Exact or fuzzy match

- **WHEN** a candidate horse matches a real runner on the card exactly or with fuzzy similarity at or above 0.6
- **THEN** the value bet is retained with its name normalized to the real runner

#### Scenario: No matching runner

- **WHEN** a candidate horse matches no real runner on the card
- **THEN** the value bet is discarded and not notified

### Requirement: Half-Kelly stake sizing scaled by Dream Stress Index

The system SHALL size a stake with half-Kelly: `kelly_stake = balance * (edge/100) * 0.5`. It SHALL scale that Kelly stake by the Dream Stress Index (DSI) — the fraction of negative dream simulations for the track:race pair. The DSI scale SHALL be 1.0 when stress is below 20%, 0.75 when stress is between 20% and 50% inclusive, and 0.50 when stress is above 50%. The final stake SHALL be the rounded value of `min(kelly_stake * dsi_scale, balance * 0.05)`, never the 5% bankroll cap.

#### Scenario: Low stress

- **WHEN** DSI is below 20%
- **THEN** the Kelly stake is scaled by 1.0 (full half-Kelly)

#### Scenario: Medium stress

- **WHEN** DSI is at least 20% and at most 50%
- **THEN** the Kelly stake is scaled by 0.75

#### Scenario: High stress

- **WHEN** DSI is above 50%
- **THEN** the Kelly stake is scaled by 0.50 (quarter-Kelly)

#### Scenario: Cap

- **WHEN** the scaled Kelly stake exceeds 5% of the bankroll
- **THEN** the final stake is capped at 5% of the bankroll

### Requirement: Hard bankroll circuit breakers

The system SHALL enforce non-negotiable hard limits when placing real-money bets: a per-bet cap of 5% of the current bankroll; stop betting once daily losses reach 20% of the current bankroll; and stop betting once drawdown reaches 50% from the peak bankroll. The daily-limit check SHALL consider today's realized loss plus open exposure plus the proposed stake.

#### Scenario: Daily limit reached

- **WHEN** today's loss plus open exposure plus the new stake reaches 20% of the current bankroll
- **THEN** the bet is blocked by the governor

#### Scenario: Max drawdown reached

- **WHEN** drawdown from peak is at least 50%
- **THEN** betting is blocked by the governor

#### Scenario: Under limits

- **WHEN** the bet is under all hard limits
- **THEN** the bet is allowed to proceed

### Requirement: Bet recording and settlement with paper awareness

The system SHALL record bets atomically (journaled with a lock) through the governor, reject recording of a below-minimum-edge bet, and, when the paper ledger is drained, refill it from the configured paper balance in place of a 0-stake ticket. On settlement the system SHALL mark the bet won/lost, credit or debit the bankroll accordingly, and wire the result/ROI to the learning engine for ROI-by-track updates.

#### Scenario: Accepted record

- **WHEN** a bet passes the edge gate and all governor checks
- **THEN** the bet is appended to history and the bankroll is debited by the stake

#### Scenario: Settlement won

- **WHEN** a bet settles as won
- **THEN** the payout is credited and the learning engine records the win by track/distance/odds

#### Scenario: Paper refill

- **WHEN** in paper mode and the paper ledger is drained below the configured floor
- **THEN** the ledger is refilled from the configured paper balance so auto-bets keep sizing on a healthy bankroll
