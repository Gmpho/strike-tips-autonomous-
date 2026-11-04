## Purpose

Provides an interactive 20-30 second animated race predictor visualizer and pacing simulation engine for South African racecards in the Strike Tips HUD, supporting both deterministic consensus and Monte Carlo value-edge modes in a dedicated panoramic sidebar view.

## ADDED Requirements

### Requirement: Interactive race simulation trigger
The system SHALL provide an interactive trigger on race cards that redirects the user to the dedicated full-page race simulation view with that race active.

#### Scenario: User launches race simulation from dashboard card
- **WHEN** user clicks the "⚡ Simulate Race" button on an active race card
- **THEN** the application navigates to the Race Simulator view with the selected race active, turf track rendered, and simulation paused at start position (0:00).

### Requirement: Dedicated sidebar view for simulation
The system SHALL provide a dedicated navigation entry in the sidebar for the Race Simulator.

#### Scenario: Accessing simulation from sidebar
- **WHEN** user clicks "Race Simulator" in the sidebar navigation
- **THEN** the full-width panoramic Race Simulator view opens with race selection carousel and live controls.

### Requirement: Dual simulation playback modes
The system SHALL support both Expected (consensus) mode and Monte Carlo (stochastic reality) mode.

#### Scenario: Running Expected mode
- **WHEN** user plays the simulation in Expected mode
- **THEN** the runners cross the finish line ordered by consensus probabilities and ratings with the favourite finishing first.

#### Scenario: Running Monte Carlo mode
- **WHEN** user plays the simulation in Monte Carlo mode
- **THEN** a stochastic outcome is calculated from true win probabilities, allowing outsiders to win in their proportional statistical scenarios.

### Requirement: Real-time finish margins and leaderboard
The system SHALL dynamically calculate and display runner margins in lengths and present a live order of finish board as horses cross the line.

#### Scenario: Race finish sequence
- **WHEN** runners cross the red finish line
- **THEN** the "Order of Finish" panel displays runner numbers, names, and finishing margins matching visual crossing times (1 length = 0.17 seconds).

### Requirement: AI Value Bet visual spotlight
The system SHALL visually distinguish the algorithm's flagged AI Value Bet with an enhanced visual aura or trail during the simulation.

#### Scenario: Value bet highlighting
- **WHEN** the race has an identified AI Value selection
- **THEN** that runner displays a distinctive purple/emerald glow and indicator during the race animation.
