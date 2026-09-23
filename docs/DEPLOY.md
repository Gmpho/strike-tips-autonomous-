# Deployment — the single truth for all three layers

The frontend is hosted on **Cloudflare Pages only** (`https://strike-tips-hud.pages.dev`).
There is no Vercel deployment — no env vars, no project state, no middleware.
`strike-tips-hud/middleware.ts`, `strike-tips-hud/vercel.json` and both `.vercel/`
directories were deleted on 2026-09-19 and must not be re-created (a resurrected
Vercel proxy would forward state-changing writes with the master key while
guarding only `/api/agent/{kill,reset}`).

> Note: the Pages build settings live in the Cloudflare dashboard, not in this
> repo. Keep them exactly as documented below.

## 1. Cloudflare Pages HUD (`strike-tips-hud/`)

- **Live URL:** <https://strike-tips-hud.pages.dev>
- The Pages project has NO git connection — deploy by hand with wrangler:
  ```bash
  npm run build   # repo root: builds strike-tips-hud, copies output to <repo>/dist/
  cd strike-tips-hud
  npx wrangler pages deploy dist --project-name strike-tips-hud
  ```
  (`functions/` is picked up from the cwd and uploaded as edge functions.)
- `functions/` is auto-detected and deployed as edge functions:
  - `functions/api/chat.ts`, `live.ts`, `transcribe.ts`, `podcast/[[route]].ts` — edge AI endpoints (secrets server-side only)
  - `functions/api/[[catchall]].ts` — reverse proxy to worker/Modal with server-side key injection
  - `functions/v1/[[catchall]].ts` — OpenAI-compatible surface
- Static behaviour: `public/_redirects` (SPA fallback), `public/_headers` (COOP/COEP)
- Verify: `GET /api/health` → worker `2.0.0` (200); `GET /api/system/health` → Modal `HEALTHY` (200)

## 2. Cloudflare Worker (`cloudflare_mcp_edge/`)

```bash
cd cloudflare_mcp_edge
node scripts/build-knowledge.js   # compiles OKF markdown → racing-knowledge.ts (also runs as predeploy)
npm run deploy                    # wrangler deploy → striketips-mcp
```

- Secrets: `BACKEND_API_URL`, `BACKEND_API_KEY`, `SEARCH_API_KEY` (optional)
- Bindings: D1 `strike-tips-racing`, KV `ODDS_KV`

## 3. Modal backend (`core_agent/`)

- Deploy: `modal deploy core_agent/core/modal_app.py`
- Entry points in `modal_app.py`: `serve_api` (keeper `min_containers=1`),
  `run_scan`, `run_odds_monitor`, `keep_warm`, plus scheduled crons
- Secrets: `strike-tips-secrets`, `strike-tips-api-key`; volume `strike-tips-data`
- Details: `docs/MODAL_README.md`

*Last verified: 2026-09-19 (all health probes HTTP 200 against the live Pages deployment).*