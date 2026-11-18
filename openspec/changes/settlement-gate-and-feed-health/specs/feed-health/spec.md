# Capability: feed-health

## Purpose

Make a non-live odds feed impossible to mistake for a live one, in both the
HUD and the logs.

## ADDED Requirements

### Requirement: Stale prices are labelled in the HUD

The dashboard SHALL surface the snapshot's `fetch_ok` and `stale` flags, and
SHALL state that prices are out of date whenever either says the feed is not
live.

#### Scenario: Odds monitor cannot refresh

- **WHEN** a snapshot arrives with `fetch_ok:false` (or `stale:true`) and it
  still carries races
- **THEN** a non-dismissable banner states the feed is not live, how long this
  tab has seen it that way, and that every price is out of date
- **AND** no race is presented as live on those prices

#### Scenario: Feed recovers

- **WHEN** a snapshot arrives with `fetch_ok:true` and `stale:false`
- **THEN** the banner disappears and the stale-since marker resets

#### Scenario: Older payload without the flags

- **WHEN** the flags are absent (older worker/proxy)
- **THEN** no banner is shown — the HUD never invents staleness

### Requirement: A circuit-breaker trip is logged once

The ATR breaker SHALL emit a single WARNING on the not-open → open transition.
Later failures while it is open SHALL log at INFO as "still open".

#### Scenario: Half-open probes keep failing

- **WHEN** failures continue past the threshold with the cooldown already
  active
- **THEN** the cooldown is not extended
- **AND** each further failure logs at INFO, so one incident reads as one
  incident
