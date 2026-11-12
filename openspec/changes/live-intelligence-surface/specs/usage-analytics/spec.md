## Purpose

Define the first-party measurement of engagement, so that watch time — the
number the live surface, the sponsor slots and any future advertising are
judged on — is a measured fact rather than an impression.

## ADDED Requirements

### Requirement: The events we already fire are recorded

The system SHALL record the engagement events the HUD already raises —
promo impressions, promo calls-to-action, promo dismissals — and the
new ones the Live surface needs (page views, Live tab opened, race
followed, watch-live activated, race card viewed). Events SHALL be sent to a
first-party endpoint and stored server-side.

#### Scenario: A promo impression is counted once
- **WHEN** a promo campaign is displayed to the user
- **THEN** exactly one impression event is recorded for that campaign and
  display

#### Scenario: A watch-live activation is recorded
- **WHEN** the user activates the watch-live control
- **THEN** a watch-live event is recorded with the race and the meeting

### Requirement: No third-party tracker, no consent surface required

The system SHALL send engagement events to a first-party endpoint and SHALL
NOT embed a third-party advertising or analytics tracker. No cookie-consent
banner SHALL be required for the measurement to work.

#### Scenario: Events leave without a third party
- **WHEN** the HUD records an engagement event
- **THEN** the event is sent to our own endpoint and no third-party
  advertising or analytics request is made

### Requirement: Watch time is derivable

The system SHALL be able to derive, per session and per surface, the time
spent and the races followed, so that the live surface's engagement can be
compared against the surfaces it replaces.

#### Scenario: The Live tab's engagement is measured
- **WHEN** a session opens the Live tab and follows two races
- **THEN** the session's time on the Live tab and the two followed races are
  derivable from the recorded events
