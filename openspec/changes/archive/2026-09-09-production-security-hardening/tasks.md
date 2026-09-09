## 1. Cloudflare Worker (`cloudflare_mcp_edge/src/index.ts`)

- [x] 1.1 Flip `isAuthorized` to `!!env.BACKEND_API_KEY && header === env.BACKEND_API_KEY`; verify unauthenticated POST/MCP → 401
- [x] 1.2 Add `ALLOWED_ORIGINS` + `corsHeaders(request)` + `OPTIONS 204` + `Vary: Origin`; verify evil origin never receives `*`
- [x] 1.3 Set `BACKEND_API_KEY` via `wrangler secret put` and `wrangler deploy`; verify with/without key probes

## 2. Vercel middleware (`strike-tips-hud/middleware.ts`)

- [x] 2.1 Add fixed-window limiter (100 req/min/IP, 429 + `Retry-After: 60`); verify over-limit behavior
- [x] 2.2 Add `SENSITIVE_PATHS` kill/reset gate on `x-api-key`/`Authorization: Bearer`, fail-closed; verify anonymous kill → 401 and Modal untouched
- [x] 2.3 `vercel env add STRIKE_TIPS_API_KEY production --force` + `vercel deploy --prod --force`; verify authorized betting/account-summary passes

## 3. Rotation + docs

- [x] 3.1 Generate 256-bit hex; rotate Modal secret (`--force`), Vercel env, Worker secret, local `.env`
- [x] 3.2 Rewrite `docs/deployment_security.md` with the 7-step procedure + curl verification probes
- [x] 3.3 Confirm old key 401s on all layers and the HUD functions with the new key
