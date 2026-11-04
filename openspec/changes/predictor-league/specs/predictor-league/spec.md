## Purpose

The predictor league is Strike Tips' free race-day community game: players submit one pick per race, picks lock before the off, winners earn published points, and a public leaderboard ranks player skill. It launches on SA race cards and accepts additional regions later without schema changes.

## ADDED Requirements

### Requirement: One pick per race per player

The system SHALL accept at most one pick per player per race. A second
submission for the same race SHALL be rejected and the original pick SHALL
stand unchanged.

#### Scenario: Duplicate pick rejected

- **WHEN** a player who already picked a runner in a race submits another pick for the same race
- **THEN** the system rejects the submission with an already-picked error and the original pick is unchanged

### Requirement: Pre-off lock

The system SHALL lock picks 5 minutes before the race off time. After the
lock, the system SHALL reject new picks and edits for that race. The lock
SHALL be enforced at the data layer so no client or API path can bypass it.

#### Scenario: Pick inside the window accepted

- **WHEN** an authenticated player submits a pick more than 5 minutes before the off
- **THEN** the pick is recorded and visible as their selection for that race

#### Scenario: Late pick rejected

- **WHEN** a player submits a pick within 5 minutes of the off or after it
- **THEN** the system rejects the submission with a locked error

#### Scenario: Edit after lock rejected

- **WHEN** a player attempts to change a pick after the race is locked
- **THEN** the system rejects the change and the original pick stands

### Requirement: Published scoring formula

Winning picks SHALL earn position points scaled by field size plus the
winner's starting-price bonus, and a value index weighted by odds beaten
(longer-odds winners earn a higher value index than shorter-odds winners,
all else equal). Non-winning picks SHALL score zero. The scoring page SHALL
publish the full formula with worked examples, and the published math SHALL
match the settlement engine exactly.

#### Scenario: Winner scores field plus bonus

- **WHEN** a player's pick wins a 12-runner race
- **THEN** the pick earns 12 position points plus the winner's starting-price bonus

#### Scenario: Loser scores zero

- **WHEN** a player's pick finishes unplaced
- **THEN** the pick earns zero points but still counts as a settled tip

#### Scenario: Longer odds earn higher value

- **WHEN** two players each win one race, one at longer odds than the other
- **THEN** the longer-odds winner receives the higher value index

### Requirement: Leaderboard ranking and eligibility

The leaderboard SHALL rank players by 30-day form rating (average points per
settled tip, normalized 0–100). It SHALL be sortable by form rating, value
index, strike rate, weekly points, and total points. Players with fewer than
5 settled tips in the last 30 days SHALL NOT appear. Players with no settled
tip in the last 7 days SHALL decay off the ranked board.

#### Scenario: Below-minimum player hidden

- **WHEN** a player has only 3 settled tips in the last 30 days
- **THEN** the player does not appear on the ranked board

#### Scenario: Inactive player decays

- **WHEN** a ranked player settles no tip for 7 consecutive days
- **THEN** the player drops off the ranked board until they settle again

#### Scenario: Sort by weekly points

- **WHEN** a viewer sorts the board by weekly points
- **THEN** rows order by points earned in the current week, descending

### Requirement: Player profiles show aggregates only

Player profiles SHALL show performance aggregates (score, strike rate,
achievements, finish-position distribution, recent form, favorite tracks,
previous winners). No profile or endpoint SHALL expose another player's
private data, stakes, or ledger entries. Display names SHALL be derived
handles, never full account identities.

#### Scenario: No private data leaks

- **WHEN** a viewer opens another player's profile
- **THEN** the response contains aggregates and public picks only, with no stakes, balances, or account identifiers

### Requirement: Points-only settlement

Picks SHALL settle to league points only and SHALL NEVER move money, stakes,
or bankroll state. Settlement SHALL use confirmed race results; a race with
no confirmed winner SHALL leave its picks pending. Settling league points
SHALL NOT alter any ledger balance.

#### Scenario: Confirmed winner settles points

- **WHEN** results confirm the winner of a locked race
- **THEN** matching picks settle to points per the published formula and non-matching picks settle to zero

#### Scenario: Unconfirmed race stays pending

- **WHEN** a race has no confirmed winner
- **THEN** its picks remain pending and no points are awarded

### Requirement: Region extensibility

Every meeting and race SHALL carry a region. The launch region set SHALL be
SA tracks; additional regions SHALL become playable without schema changes.

#### Scenario: New region plugs in

- **WHEN** a meeting with a newly added region is published
- **THEN** its races accept picks, locks, scoring, and ranking through the same paths as SA races

### Requirement: One human one account

Each player identity SHALL be bound to a single verified Telegram link, and
the system SHALL reject binding a link that is already attached to another
player.

#### Scenario: Duplicate link rejected

- **WHEN** a registration attempt presents a Telegram link already bound to an existing player
- **THEN** the system rejects the registration with an already-linked error
