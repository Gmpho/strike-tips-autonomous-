# Capability: promohub

## Purpose

Curious signups become linked core users through targeted, snoozable promos.

## ADDED Requirements

### Requirement: Targeted display

A campaign SHALL render only when ALL its targeting rules pass (session,
link state, install state, view history, snooze).

#### Scenario: Linked user never sees connect promo
- **WHEN** the user has a LINKED telegram state
- **THEN** the Telegram-connect campaign is excluded

### Requirement: Snooze, not nag

Dismissing a campaign SHALL hide it for 7 days; betting views SHALL never
host popups.

#### Scenario: Dismissed PWA promo
- **WHEN** the user dismisses the install card
- **THEN** it stays hidden for 7 days, then becomes eligible again

### Requirement: Funnel telemetry

Impressions, dismissals, and CTA taps SHALL emit telemetry events for the
curious-to-core funnel.

#### Scenario: CTA tap
- **WHEN** the user taps a campaign CTA
- **THEN** a `promo_cta` event records campaign id + action
