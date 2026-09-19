## MODIFIED Requirements

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