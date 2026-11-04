# edge-csp Specification

## Purpose
TBD - created by archiving change harden-pages-functions. Update Purpose after archive.

## Requirements

### Requirement: HUD documents carry Content-Security-Policy

Pages `_headers` SHALL deliver a `Content-Security-Policy-Report-Only` policy
on document responses allowing: scripts and frames from `'self'` and
`https://challenges.cloudflare.com`, connections to `'self'` and the LLM API
hosts the edge already calls, inline styles required by the UI stack, and
nothing for `object-src`. Enforcement MAY flip to reporting mode `off` only
after a documented violation-free observation period.

#### Scenario: Report-Only header present on documents

- **WHEN** a browser loads any HUD document
- **THEN** the response carries `Content-Security-Policy-Report-Only` covering script, frame, connect, style, and object sources

#### Scenario: Turnstile and LLM hosts stay functional

- **WHEN** the session bootstrap loads the Turnstile widget and a chat call reaches its provider
- **THEN** neither is blocked by the policy
