## Why

Vercel Hobby caps blown (30.1/10 GB transfer, 5h10m/4h CPU, 387/360 GB-hrs) paused the HUD mid-race-day. Every dashboard poll (5s/15s) spun a Fluid function that only proxied to Modal. Cloudflare Pages serves the same static bundle with unlimited bandwidth free.

## What Changes

* HUD hosted on Cloudflare Pages (`strike-tips-hud.pages.dev`); Vercel kept paused as fallback.
* Keyless reads go direct browser→origin (Modal SAFE_PATHS + MCP worker), zero Function invocations.
* Keyed endpoints proxied by Pages Functions (`functions/api`, `functions/v1`) with server-side secret injection, 100 req/min/IP guard, fail-closed sensitive paths.
* Poll cadence trimmed (fast 5s→15s, slow 15s→60s); SSE stays the live channel.
* Backends emit `Cross-Origin-Resource-Policy: cross-origin` so direct fetches pass the COEP document; Modal + worker CORS allowlists gain the pages.dev origin.

## Capabilities

### New Capabilities
- `cloudflare-hud-hosting`: Pages static hosting with direct-origin reads and Function proxy for keyed endpoints.

### Modified Capabilities
- (none)

## Impact

* `strike-tips-hud/src/lib/backend-origin.ts` (new), `api-fetch.ts`, `engine/data-bridge.ts`
* `strike-tips-hud/functions/api/[[catchall]].ts`, `functions/v1/[[catchall]].ts`, `public/_headers`, `public/_redirects`
* `core_agent/api_pkg/__init__.py` (CORS + CORP), `cloudflare_mcp_edge/src/index.ts` (CORS + CORP)
* Secrets: `BACKEND_API_KEY` on Pages production.
