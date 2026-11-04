# api-resilience Specification

## Purpose
TBD - created by archiving change harden-pages-functions. Update Purpose after archive.

## Requirements

### Requirement: Upstream failures return structured JSON, never crash pages

The reverse proxy SHALL catch upstream failures on both the primary and
fallback legs and return a JSON 502 envelope (`error`, `upstream`,
`retryable`) with `Retry-After` instead of rethrowing. The fallback leg SHALL
carry the same abort timeout as the primary leg. The success path — including
streaming response bodies — passes through unchanged.

#### Scenario: Modal outage returns a structured 502

- **WHEN** the primary upstream fetch rejects during a Modal outage
- **THEN** the proxy returns a JSON 502 envelope naming the upstream and marks the response retryable

#### Scenario: Fallback leg is timeout-bounded

- **WHEN** the fallback-leg fetch is issued
- **THEN** it carries the same abort timeout as the primary leg

### Requirement: In-memory limiter state is bounded

Every in-memory rate-limit store SHALL evict expired entries on window
rollover and SHALL enforce a hard key cap with oldest-expiry eviction, so no
isolate's limiter memory grows without bound under spoofed-IP load.

#### Scenario: Store stays bounded under spoofed IPs

- **WHEN** many distinct spoofed IPs hit the limiter within one window
- **THEN** the store size never exceeds the configured hard cap

### Requirement: Write-family guards are prefix-complete

Every declared write-family prefix SHALL be normalized (no trailing slash) at
declaration time so the guard covers both the family's exact path and its
subpaths. The `/api/tasks` family SHALL guard `POST /api/tasks` and
`POST /api/tasks/*` alike.

#### Scenario: Exact tasks path is guarded

- **WHEN** `POST /api/tasks` arrives with no caller key and no session token
- **THEN** the proxy returns 401 and Modal is never contacted

#### Scenario: Subpath tasks guard is unchanged

- **WHEN** `POST /api/tasks/123/run` arrives with no caller key
- **THEN** the proxy returns 401 and Modal is never contacted
