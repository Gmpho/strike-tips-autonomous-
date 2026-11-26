## Purpose

Makes upstream failure reporting accurate so operators can distinguish a
blocked bookmaker, a blocked cloud egress and a genuinely empty card, and can
trust that a documented production path is actually the one running.

## ADDED Requirements

### Requirement: Layer-accurate upstream block reporting

When an upstream request is refused, the emitted diagnostic MUST identify the
actual refusing layer, the HTTP status and the egress colo when the runtime
exposes it. Diagnostics MUST NOT attribute a Cloudflare WAF refusal to the
upstream price source, or vice versa.

#### Scenario: Price source refuses the request

- **WHEN** the price source answers with a WAF block page to the backend's datacentre egress
- **THEN** the log states the source name, the HTTP status and the observed colo
- **AND** it does not claim a network failure or an empty race card

#### Scenario: Edge platform refuses the backend

- **WHEN** the edge hostname refuses a backend request before any upstream call is made
- **THEN** the log states that the edge platform blocked the backend egress
- **AND** it does not describe the response as a price source refusal

#### Scenario: Scheduled run executes in a refused location

- **WHEN** a scheduled invocation cannot reach the upstream from its own colo
- **THEN** the diagnostic records the scheduled nature and the refusal
- **AND** it identifies the request-driven path as the active fetch when that path is succeeding

### Requirement: No false production-path claims

Diagnostics, comments and operator-facing messages MUST describe the fetch path
that is actually producing fresh data. A path that has never written data MUST
NOT be described as the production fetch.

#### Scenario: Retired path is no longer advertised

- **WHEN** a scheduled fetch has produced no stored price payload while request-driven fetches have
- **THEN** operator-facing text no longer describes the scheduled fetch as the production path
- **AND** the active path is named explicitly

#### Scenario: Colo names match observed values

- **WHEN** a diagnostic mentions an egress colo
- **THEN** the colo is one actually observed in runtime telemetry for that path

### Requirement: Honest age and provenance of prices

A price or field value reused from an earlier cycle MUST be reported as such.
The system MUST NOT present a card as live when its newest price is older than
the configured freshness window.

#### Scenario: Carried price is labelled

- **WHEN** a runner receives a price restored from a previous cycle
- **THEN** the payload carries a carry-forward marker for downstream consumers
- **AND** any age indicator reflects the older observation, not the publish time

#### Scenario: Empty card is not invented

- **WHEN** every upstream source returns no prices
- **THEN** runners remain unpriced and a warning is emitted
- **AND** no price, form value or rating is fabricated

### Requirement: Neutral HUD-facing wording

Operator-facing text rendered in the HUD MUST NOT name any bookmaker or wagering
brand.

#### Scenario: Generic labels are preserved after refactor

- **WHEN** a decomposed module supplies a label shown in the HUD
- **THEN** that label is generic and contains no bookmaker name
- **AND** existing generic labels such as form insight remain unchanged
