## Purpose

Define the punter-facing `Live` surface: the race in play, its prices and
movement, the AI read reacting to that movement, the user's own league pick
in the race, the result and settlement afterwards — and the navigation names
that make each surface say what it is.

## ADDED Requirements

### Requirement: A Live tab shows one meeting's race in play

The system SHALL provide a `Live` tab that shows a single meeting and the
race within it that is currently running or next off, with the race number,
the off time, the elapsed time since the off, and a switcher for the
meetings the user can see. The tab SHALL present the runners of that race
with their current prices and the movement in those prices.

#### Scenario: The live race is identifiable
- **WHEN** the user opens the Live tab during a racing window
- **THEN** the tab shows the race that is running or next off, with its off
  time and the time elapsed since it

#### Scenario: The meeting switcher covers the visible card
- **WHEN** the card holds meetings from more than one region
- **THEN** the switcher lists those meetings and the selected one is the
  meeting whose race is in play

### Requirement: Movement is shown where the punter chooses

The system SHALL show price movement on the runners of the live race —
direction, size, and the percentage change — and SHALL reuse the existing
movement components so the Movers tab and the Live tab cannot drift apart.
A runner's movement SHALL be identified as the user's pick where that is
the case.

#### Scenario: A steamer is visible on the live race
- **WHEN** a runner on the live race has shortened by more than the
  steamer threshold
- **THEN** the runner is shown as a steamer with its price and the size of
  the move

### Requirement: The user's own pick is the centrepiece

The system SHALL show the user's league pick for the live race, with its
price, the movement in that price, and the state of the pick. Where the
race has finished, the tab SHALL show the result, the settlement of the
pick, the points it earned, and the resulting leaderboard movement.

#### Scenario: The punter's pick is running
- **WHEN** the user holds a league pick in the live race
- **THEN** the tab shows that pick, its price and the movement in that price

#### Scenario: The pick has been settled
- **WHEN** the live race has finished and the pick has been settled
- **THEN** the tab shows the finishing position, the points earned and the
  leaderboard change

### Requirement: The AI read reacts to the movement

The system SHALL show an in-play read for the live race that accounts for
the price movement observed, and SHALL state plainly when a move has
overtaken the system's own estimate — so a punter is not told a value is
intact while the market is moving against it.

#### Scenario: The market chases the value
- **WHEN** the runner the system rates as value has shortened sharply
- **THEN** the read states that the market has chased the runner and that
  the system's edge is fading or gone

### Requirement: A watch-live control appears only on the live race

The system SHALL provide a control that opens the race on the broadcaster's
own page. The control SHALL appear only for the race that is live, SHALL
never appear as a row of controls on every card, and SHALL NOT embed,
proxy or re-stream any picture. The control SHALL work with no partner
agreement, and the tab SHALL stay usable when the broadcaster's page is
unavailable.

#### Scenario: One control, one race
- **WHEN** a meeting has several races on the card
- **THEN** only the live race carries the watch-live control

#### Scenario: The link leaves for the rights holder
- **WHEN** the punter activates the watch-live control
- **THEN** the broadcaster's own page opens with the race, and the Live tab
  remains available with the data, the pick and the result

### Requirement: Navigation names each surface once

The system SHALL rename the agent-telemetry view from `Live Ops` to
`Engine Ops` and SHALL keep `Logs` as the name of the audit trail. The
`Live Races × Stories` content SHALL move from the engine view into the
`Live` tab. Existing route ids and URLs SHALL continue to resolve, and
aliases SHALL exist for the new names.

#### Scenario: An old link still works
- **WHEN** a user opens `/logs` or `/telemetry`
- **THEN** the corresponding view opens as before

#### Scenario: The new names are reachable
- **WHEN** a user opens `/engine-ops` or `/live`
- **THEN** the engine view and the Live tab open respectively

#### Scenario: Races × news lives with the race
- **WHEN** the user views the Live tab
- **THEN** the race-linked news stories are shown there, and the engine view
  contains only engine telemetry
