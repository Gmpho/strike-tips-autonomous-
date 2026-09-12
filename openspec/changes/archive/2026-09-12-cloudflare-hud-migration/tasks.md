## 1. Backend headers

- [x] 1.1 Modal CORS gains `strike-tips-hud.pages.dev` + `CORP: cross-origin`; deployed and verified (GET + preflight)
- [x] 1.2 MCP worker allowlist gains pages.dev + CORP; `npm run deploy` green

## 2. HUD rewire

- [x] 2.1 `backend-origin.ts` keyless routing (CF + Modal sets), `api-fetch.ts` rewrite (strings only)
- [x] 2.2 Poll cadence 15s/60s

## 3. Pages shell

- [x] 3.1 `functions/api` + `functions/v1` proxies (routing, secret injection, rate-limit, sensitive auth)
- [x] 3.2 `public/_headers` (COOP/COEP) + `public/_redirects` (SPA fallback)

## 4. Deploy + verify

- [x] 4.1 `npm run build`, project create, `BACKEND_API_KEY` secret, deploy; prod 200
- [x] 4.2 Browser: dashboard 127 events/68 stamped, card Days/Gear/Owner, capital PAPER, exotics/news/open 200, zero console errors
