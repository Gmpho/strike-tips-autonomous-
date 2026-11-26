## Purpose

Lets the Cloudflare edge worker be split into smaller routing and support units
without changing the HTTP, MCP or cache contract that the HUD and backend rely
on.

## ADDED Requirements

### Requirement: Route and response parity

Every existing REST and MCP route MUST keep its path, allowed methods,
authentication rule, CORS headers, status codes and response shape after the
split. No route may be removed, renamed or moved to a different host.

#### Scenario: HUD polling still succeeds

- **WHEN** the HUD requests a full racing card from the edge after decomposition
- **THEN** the response has the same status, headers and JSON shape as before
- **AND** the producer label and freshness fields in the payload are unchanged

#### Scenario: MCP clients are unaffected

- **WHEN** an MCP client calls an existing tool endpoint after decomposition
- **THEN** authentication, transport mode and tool result shape are unchanged

### Requirement: Binding and storage parity

Binding names, KV key names, D1 database identity and exported environment
variables MUST remain unchanged. Cache freshness and TTL behaviour MUST be
preserved.

#### Scenario: Snapshot cache still resolves

- **WHEN** the backend pushes a snapshot and the HUD reads it after decomposition
- **THEN** the same KV key is used and the same "freshest card wins" selection applies
- **AND** TTL and per-slot rotation semantics are unchanged

#### Scenario: No new writes to protected stores

- **WHEN** the split edge code is deployed
- **THEN** it writes only to the keys it wrote before
- **AND** no settlement, ledger or bankroll store receives new writes

### Requirement: Traffic-triggered refresh is preserved

The full-card odds route MUST continue to trigger a rate-limited background
price fetch from the request's colo, because scheduled invocations run in a
colo that the price sources refuse. The hourly scheduled fallback MUST remain
registered, and total KV writes MUST stay within the free-tier daily allowance.

#### Scenario: A HUD poll refreshes prices in the background

- **WHEN** a full-card odds request arrives from a colo whose egress the price source accepts
- **THEN** a background fetch is registered without delaying the response
- **AND** fresh price payloads are parked in the same KV keys the backend already reads

#### Scenario: Parallel polls cannot stampede

- **WHEN** many card polls arrive within the refresh interval
- **THEN** at most one background fetch starts in that interval
- **AND** no fetch is started solely by a per-track or per-race query

#### Scenario: Scheduled fallback stays cheap

- **WHEN** a full day elapses with continuous HUD polling
- **THEN** the scheduled fallback runs at most hourly
- **AND** total KV writes remain below the free-tier daily limit

### Requirement: Secrets are never exposed

API keys and tokens MUST NOT appear in responses, logs or diagnostics produced
by any extracted routing module.

#### Scenario: Error path does not leak credentials

- **WHEN** an upstream request fails after decomposition
- **THEN** the emitted diagnostic contains status and source name only
- **AND** no key, token or authorization header value is present
