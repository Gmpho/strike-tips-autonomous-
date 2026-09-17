## Purpose

Close the authenticated perimeter around paid compute and state changes without breaking the keyless HUD.

## ADDED Requirements

### Requirement: Keyed inference and sockets

`/v1/*` and `/ws/chat` SHALL require a valid API key (header, Bearer, or WS `api_key` query). SAFE_PATHS and `/mcp` stay open. A missing server key SHALL deny everything.

#### Scenario: Anonymous chat attempt
- **WHEN** `POST /v1/chat/completions` arrives without a key
- **THEN** it returns 401 and no provider is touched

#### Scenario: HUD chat unaffected
- **WHEN** the HUD posts via the Pages proxy (which injects the server key)
- **THEN** it receives 200 as before

### Requirement: Proxy least-privilege

The Pages api Function SHALL require a caller-presented key for state-changing families (betting, config, healing, tasks, agent kill/reset) and SHALL cap writes at 20/min/IP. Reads keep server-side injection.

#### Scenario: Anonymous bet placement
- **WHEN** `POST /api/betting/place` arrives without a caller key
- **THEN** it returns 401 before touching the backend

### Requirement: PIN brute-force lockout

Five failed `/auth` PIN attempts SHALL lock a chat out for 30 minutes; success SHALL clear the record. State SHALL live on the shared volume so all containers enforce it.

#### Scenario: Sixth guess
- **WHEN** a chat fails PIN entry 5 times
- **THEN** the 6th attempt (even correct) is refused until the window lapses
