## ADDED Requirements

### Requirement: Keyless AI surface has global and concurrency ceilings

`/api/live` SHALL cap concurrent sessions per IP (1), cap total concurrent
sessions isolate-wide, and throttle client frames relayed upstream per
session, rejecting excess with 429. `/api/chat` SHALL enforce a global
per-window request ceiling isolate-wide in addition to its per-IP limit.
Global ceilings are per-isolate best-effort by documented limitation.
Per-call caps already in place (`max_tokens: 1500`, body limit) SHALL be
pinned, not weakened.

#### Scenario: Second live session per IP is rejected

- **WHEN** an IP with an active live session requests another WebSocket upgrade
- **THEN** the edge returns 429 without opening an upstream session

#### Scenario: Global live ceiling holds isolate-wide

- **WHEN** concurrent live sessions across all IPs reach the global cap
- **THEN** further upgrades receive 429 until an active session closes

#### Scenario: Client frame flood is throttled

- **WHEN** a client sends frames beyond the per-session message rate
- **THEN** excess frames are dropped and the upstream connection stays within the relay budget

#### Scenario: Chat global ceiling backs the per-IP limit

- **WHEN** total chat requests in the current window reach the global cap
- **THEN** further chat requests receive 429 regardless of IP

#### Scenario: Per-call spend caps stay pinned

- **WHEN** any chat request is forwarded upstream
- **THEN** it carries the existing per-call caps (max tokens 1500, 32 KB body limit) unchanged