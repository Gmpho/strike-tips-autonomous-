## Why

A production inspection found the API effectively public: the Vercel
middleware forwarded every request to Modal with the key injected at the
edge and no authorization check (the kill switch was triggerable by anyone
via curl, bankroll and chat history fully exposed), and the Cloudflare
Worker's `isAuthorized` returned true for every request whenever
`BACKEND_API_KEY` was empty — exposing all 16 MCP tools, D1, and KV. CORS
was a wildcard and the middleware had no rate limiting, leaving the Modal
free tier open to denial-of-service.

## What Changes

- Cloudflare Worker `isAuthorized` is fail-closed: requires a non-empty
  `BACKEND_API_KEY` AND a matching `x-api-key` header.
- CORS allowlist replaces `*` (production HUD origin + localhost dev), with
  `OPTIONS` preflight handling and `Vary: Origin`.
- Vercel middleware gains fixed-window rate limiting (100 req/min per IP,
  `429` + `Retry-After`) and requires `x-api-key`/`Authorization: Bearer`
  for sensitive endpoints (`/api/agent/kill`, `/api/agent/reset`) —
  fail-closed when no expected key is configured.
- Secrets rotated to a fresh 256-bit hex across Modal, Vercel, Cloudflare,
  and local `.env`; rotation procedure documented.

## Capabilities

### New Capabilities
- `production-security`: edge auth, CORS policy, rate limiting, and secret
  rotation for the 3-layer stack.

### Modified Capabilities
(none — no prior spec covered security.)

## Impact

- `cloudflare_mcp_edge/src/index.ts` (auth, CORS helpers, preflight)
- `strike-tips-hud/middleware.ts` (rate limiter, sensitive-path auth)
- `docs/deployment_security.md` (7-step rotation for Modal/Vercel/Cloudflare)
- Secrets: `strike-tips-api-key` (Modal), `STRIKE_TIPS_API_KEY` (Vercel),
  `BACKEND_API_KEY` (Cloudflare Worker + local `.env`)
- Verified live: `POST /api/agent/kill` without key → 401 (was EMERGENCY
  STOP), evil-origin CORS → production origin only, Modal accepts new key.
