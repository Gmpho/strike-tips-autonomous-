# cloudflare-hud-hosting Specification

## Purpose
Serve the HUD from Cloudflare Pages with unlimited free bandwidth while keeping secrets server-side and backend load unchanged.

## Requirements

### Requirement: Static hosting on Pages

The production HUD SHALL be served from `https://strike-tips-hud.pages.dev` with SPA fallback (`/*` → `/index.html`) and COOP/COEP headers preserved for Wasm workers.

#### Scenario: Deep link loads
- **WHEN** a user opens `/dashboard` directly
- **THEN** the SPA shell loads with HTTP 200 (no 404)

### Requirement: Direct keyless reads

Keyless GET/POST endpoints (Modal SAFE_PATHS + MCP worker paths) SHALL be fetched direct browser→origin, bypassing Pages Functions entirely.

#### Scenario: Poll Skips proxy
- **WHEN** the HUD polls `/api/system/health`
- **THEN** the request goes to Modal directly and no Function invocation is logged

### Requirement: Proxied keyed endpoints

Keyed/endpoints SHALL stay same-origin and be forwarded by the Pages Function with the secret injected server-side; sensitive paths (`kill`, `reset`) SHALL require a caller key (fail-closed); callers SHALL be rate-limited at 100 req/min/IP.

#### Scenario: Bankroll summary loads without client secret
- **WHEN** the HUD requests `/api/betting/account-summary` with no key
- **THEN** it receives HTTP 200 with live balances

### Requirement: Backend cross-origin headers

Modal and the MCP worker SHALL allow the pages.dev origin via CORS and SHALL emit `Cross-Origin-Resource-Policy: cross-origin` so direct fetches pass the COEP document.

#### Scenario: Preflight from Pages
- **WHEN** the browser preflights `POST /api/agent/chat` from pages.dev
- **THEN** it receives HTTP 200 with the Pages origin allowed
