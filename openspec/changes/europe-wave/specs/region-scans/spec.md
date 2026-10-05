# Capability: europe-wave

## Purpose

International scans run manifest-only (today's carded meetings), region by
region, on their own clock — never an 84-track sweep.

## ADDED Requirements

### Requirement: Manifest-only international scans

Region scans SHALL touch only meetings listed in the day's TAB manifest for
the requested regions.

#### Scenario: UK/IRE day
- **WHEN** the manifest lists Kempton (UK) and Vaal (no region tag match)
- **THEN** the scan covers Kempton only, in digest-only mode

### Requirement: Digest-only Europe wave

The Europe scan SHALL send the Europe Intelligence Report with no auto-bets,
no individual alerts, and no memory writes.

#### Scenario: Value found in Europe
- **WHEN** a European meeting yields value flags
- **THEN** they appear in the digest; bankroll and memory are untouched
