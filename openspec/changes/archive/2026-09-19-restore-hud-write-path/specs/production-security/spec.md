## MODIFIED Requirements

### Requirement: Middleware rate limiting and sensitive-path auth

The edge proxy middleware SHALL rate-limit to 100 requests/minute per IP (429 + `Retry-After: 60` over the limit) and SHALL require a matching API key for `/api/agent/kill` and `/api/agent/reset`, returning 401 otherwise — including when no expected key is configured. A browser session token (proof-of-browser for legitimate writes such as settings and healing) SHALL NEVER satisfy these two paths: the master-key check runs first and independently of any token.

#### Scenario: Anonymous kill switch blocked

- **WHEN** `POST /api/agent/kill` arrives without `x-api-key`
- **THEN** the proxy returns 401 and Modal is never contacted

#### Scenario: Session token fails the kill switch

- **WHEN** `POST /api/agent/kill` arrives bearing a valid browser session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted

#### Scenario: Session token fails reset

- **WHEN** `POST /api/agent/reset` arrives bearing a valid browser session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted