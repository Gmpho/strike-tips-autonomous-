# browser-write-auth Specification

## Purpose
Defines the edge-minted proof-of-browser session token the HUD uses for legitimate writes: who gets one, what it unlocks, what it can never unlock, and the HUD's obligation to verify responses before reflecting state.

## Requirements

### Requirement: Session tokens are issued edge-side to verified browsers

The edge SHALL mint a short-lived signed browser session token only to a browser that passes a Turnstile challenge, only when no valid token is already present, and without requiring or recording any user identity. Verification SHALL be a local signature check with no upstream call on the hot path.

#### Scenario: Verified browser receives a token

- **WHEN** a browser without a valid token passes the Turnstile challenge
- **THEN** the edge SHALL return a signed token with a short lifetime

#### Scenario: Token check costs no upstream call

- **WHEN** a request arrives bearing a session token
- **THEN** verification SHALL be a local signature check with no fetch to any backend

#### Scenario: Public site key is served without exposing the secret

- **WHEN** the HUD requests the session configuration (`GET /api/session`)
- **THEN** the edge SHALL return the Turnstile site key and an enabled flag, and SHALL NOT return the Turnstile secret, the session secret, or the backend key

### Requirement: Legitimate writes accept the session token

The reverse proxy SHALL accept a valid browser session token as proof-of-browser for the legitimate write families (`/api/config*`, `/api/healing/*`, `/api/dreaming/*`) and SHALL forward those calls with the master key injected server-side, exactly as it does today for reads. All other acceptance rules (`WRITE_PREFIXES`, rate limits, master-key checks) keep their current semantics.

#### Scenario: Token-bearing settings save reaches the backend

- **WHEN** `POST /api/config` arrives bearing a valid session token and no master key
- **THEN** the proxy SHALL forward it with the master key injected and SHALL NOT return 401

#### Scenario: Master-key path still works

- **WHEN** `POST /api/config` arrives bearing the master key and no session token
- **THEN** the proxy SHALL forward it unchanged

### Requirement: Sensitive actions stay master-key-only

A browser session token SHALL NEVER satisfy `/api/agent/kill`, `/api/agent/reset`, or any other master-key-only action. The decision logic SHALL check the master key first and independently of any token, so token acceptance can never broaden by accident.

#### Scenario: Session token fails the kill switch

- **WHEN** `POST /api/agent/kill` arrives bearing a valid session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted

#### Scenario: Session token fails reset

- **WHEN** `POST /api/agent/reset` arrives bearing a valid session token but no master key
- **THEN** the proxy SHALL return 401 and Modal is never contacted

### Requirement: HUD reflects verified server state only

The HUD SHALL flip no lock, armed, or saved state until the write response verifies (`res.ok`) and its body confirms the requested state: the emergency-stop control requires the response body's `status` field to match the requested state (`locked` for kill, `active` for reset), and settings writes require a success body. Any failed or unconfirmed write SHALL render an error state instead of an optimistic success. When the Turnstile challenge itself fails, expires, or is dismissed, the HUD SHALL render an explicit verification-failed state with a retry affordance instead of closing silently — the caller SHALL receive a distinguishable `challenge-failed` outcome rather than a bare write failure.

#### Scenario: Kill fails, UI stays unlocked

- **WHEN** `POST /api/agent/kill` returns a non-2xx status
- **THEN** the agent-status control SHALL keep displaying "unlocked" and SHALL render an error state

#### Scenario: Kill response confirms the locked state before the UI flips

- **WHEN** `POST /api/agent/kill` returns 2xx with a body whose `status` is `locked`
- **THEN** the agent-status control SHALL display "locked"

#### Scenario: Mismatched body is treated as a failure

- **WHEN** `POST /api/agent/kill` returns 2xx but its body does not confirm the requested state (`status` is not `locked`)
- **THEN** the agent-status control SHALL NOT display "locked" and SHALL render an error state

#### Scenario: Settings save fails, failure is visible

- **WHEN** `POST /api/config` returns a non-2xx status
- **THEN** the settings view SHALL render the failure instead of appearing saved

#### Scenario: Challenge failure is visible and retryable

- **WHEN** the Turnstile widget errors, expires, or the user dismisses it during the bootstrap flow
- **THEN** the HUD SHALL show an explicit verification-failed state with a retry affordance, and the write SHALL fail as `challenge-failed` rather than a generic error
