# production-security Specification

## Purpose
Defines the authentication, cross-origin, rate-limit, and secret-rotation
rules that keep the racing API private across the Cloudflare →
Modal layers. Every control fails closed: a missing secret denies, never
permits.

## Requirements

### Requirement: Fail-closed worker authorization

`isAuthorized` SHALL return true only when `BACKEND_API_KEY` is non-empty
AND the request's `x-api-key` header equals it. POST ingest endpoints and
`/mcp` SHALL reject unauthorized callers with 401.

#### Scenario: Empty secret denies all
- **WHEN** `BACKEND_API_KEY` is unset and any POST/MCP request arrives
- **THEN** the worker responds 401 instead of authorizing

#### Scenario: Wrong key rejected
- **WHEN** `x-api-key` does not match the configured secret
- **THEN** the worker responds 401

### Requirement: Restricted CORS

The worker SHALL echo only allowlisted origins (`strike-tips-hud.pages.dev`
plus localhost dev ports), SHALL answer `OPTIONS` preflight with 204 and the
CORS headers, and SHALL send `Vary: Origin`. The wildcard `*` SHALL NOT
appear on API responses.

#### Scenario: Evil origin contained
- **WHEN** a request arrives with `Origin: https://evil.com`
- **THEN** `Access-Control-Allow-Origin` is the production origin, never `*`

### Requirement: Middleware rate limiting and sensitive-path auth

The edge proxy middleware SHALL rate-limit to 100 requests/minute per IP (429 + `Retry-After: 60` over the limit) and SHALL require a matching API key for `/api/agent/kill` and `/api/agent/reset`, returning 401 otherwise — including when no expected key is configured. A browser session token (proof-of-browser for legitimate writes such as settings and healing) SHALL NEVER satisfy these two paths: the master-key check runs first and independently of any token. Rate-limit state SHALL be bounded: stores SHALL evict expired entries on window rollover and enforce a hard key cap, and every declared write-family prefix SHALL be normalized (no trailing slash) at declaration time so guards cover both exact paths and subpaths — `POST /api/tasks` with no caller key or session token SHALL be rejected 401 with no upstream contact.

#### Scenario: Anonymous kill switch blocked

- **WHEN** `POST /api/agent/kill` arrives without `x-api-key`
- **THEN** the proxy returns 401 and Modal is never contacted

#### Scenario: Session token fails the kill switch

- **WHEN** `POST /api/agent/kill` arrives bearing a valid browser session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted

#### Scenario: Session token fails reset

- **WHEN** `POST /api/agent/reset` arrives bearing a valid browser session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted

#### Scenario: Exact tasks path is guarded

- **WHEN** `POST /api/tasks` arrives with no caller key and no session token
- **THEN** the proxy returns 401 and Modal is never contacted

### Requirement: Secret rotation

Rotation SHALL generate 256-bit hex (`openssl rand -hex 32`) and SHALL apply
it to all four stores (Modal secret, Cloudflare Pages env, Cloudflare worker secret,
local `.env`); the rotation runbook SHALL live in
`docs/deployment_security.md` with curl probes for verification.

#### Scenario: Old key dead after rotation
- **WHEN** rotation completes
- **THEN** requests bearing the previous key receive 401 on every layer

### Requirement: Chroma compound filters

Multi-condition Chroma `where` clauses SHALL use `$and` syntax. Single-condition filters are unchanged.

#### Scenario: Freshness gate query
- **WHEN** checking today's insight for a horse/course/region
- **THEN** the query returns matches instead of throwing, and rebuilt insights stop wasting Groq calls
