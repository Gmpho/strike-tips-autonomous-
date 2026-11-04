# Tasks: Chat Edge Search Cascade

## 1. Edge contract

- [x] 1.1 Confirm live edge `web_search_racing` returns `provider: "tavily"` with results (prod MCP probe) — verified 2026-09-28 (`provider: "tavily"`, 5 results)
- [x] 1.2 Confirm no worker change is needed: chat reuses `/mcp` JSON-RPC + `x-api-key` and verify the endpoint is unchanged

## 2. Pages Functions

- [x] 2.1 Add `functions/lib/edge-search.ts` (cascade client + context builder) and verify `npx tsc --noEmit` is clean (exit=0)
- [x] 2.2 `functions/api/chat.ts`: inject cascade results for all models, pass sources to both handlers, remove the `googleSearch` tool — verify tsc clean + no `googleSearch` references remain
- [x] 2.3 Add `functions/api/search.ts` keyless rate-limited JSON proxy — verify route file exists and tsc clean
- [x] 2.4 Document the secret fallback chain (`MCP_API_KEY` → `STRIKE_TIPS_API_KEY` → `BACKEND_API_KEY`) in the change notes — written in proposal/design

## 3. HUD

- [x] 3.1 Search control visible for all model choices + label kept on mobile; source chips attributed to the cascade — verify `npm run build` (✓ built in 1m 2s)
- [x] 3.2 WebLLM path: fetch `/api/search` when the toggle is on, append results to the compiled context, attach sources to the message — verify build

## 4. Verification

- [x] 4.1 `npm run build` green in `strike-tips-hud/` (tsc + vite: ✓ built in 1m 2s)
- [x] 4.2 Python suite unaffected: `python3 -m pytest core_agent/tests/ -q` — 351 passed / 4 failed / 3 errors, all pre-existing env issues (missing fastapi on host, snapshot-integrity mtime), zero Python files touched by this change; Docker daemon unavailable 2026-09-28
- [ ] 4.3 Re-run prod probes after deploy (edge health, Modal health, Pages HUD 200) — deploy is the user's call
- [ ] 4.4 Live chat probe: one search turn returns `groundingSources` from the cascade (not Google) — after deploy

