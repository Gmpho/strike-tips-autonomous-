# Deployment Security

## 🛡️ Security Overview (2026-09-02 Hardening)
Strike Tips employs defense-in-depth across the 3-layer stack:

* **Cloudflare Worker (`cloudflare_mcp_edge/src/index.ts:20`):** `isAuthorized` now `!!env.BACKEND_API_KEY && header===env.BACKEND_API_KEY` (fail-closed, was `!env.BACKEND_API_KEY ||` open when empty). CORS `*` replaced with `ALLOWED_ORIGINS` allowlist (`https://strike-tips-hud.vercel.app` + localhost) + `OPTIONS 204` + `Vary: Origin` (`src/index.ts:31`).
* **Vercel Middleware (`strike-tips-hud/middleware.ts:14`):** fixed-window `100 req/min` per IP (`429 Retry-After:60`), `SENSITIVE_PATHS` (`/api/agent/kill`, `/api/agent/reset`) require `x-api-key` (`401` without).
* **Modal Backend (`core_agent/core/security.py:35`):** `X-API-KEY` check except `SAFE_PATHS`; `STRIKE_TIPS_API_KEY` via `modal.Secret`.

See `docs/RELEASE_2026_09_02_SECURITY_BETFAIR_MOBILE.md` §A for `curl` probes and rotation verification.

## 🔑 Managing API Keys (Rotate `STRIKE_TIPS_API_KEY` / `BACKEND_API_KEY`)

Use `openssl rand -hex 32` (256-bit, 64 hex chars) — the 2026-09-02 rotation used `7a70174b1f0d6bfa84009329b9800d5013c768fc52d2b1be77084c465201a125`.

### Rotate (All 3 Layers)

1. **Generate:** `openssl rand -hex 32`
2. **Local `.env`:** set `STRIKE_TIPS_API_KEY="<new>"` (`.env:5`)
3. **Modal:** `modal secret create strike-tips-api-key STRIKE_TIPS_API_KEY=<new> --force` (read via `core_agent/core/security.py:5`)
4. **Vercel:** `printf "<new>" | vercel env add STRIKE_TIPS_API_KEY production --force` then `vercel deploy --prod --force --cwd strike-tips-hud`
5. **Cloudflare:** `printf "<new>" | npx wrangler secret put BACKEND_API_KEY` (in `cloudflare_mcp_edge/`) then `npx wrangler deploy` (`src/index.ts:20` reads `env.BACKEND_API_KEY`)
6. **Restart local Docker if used:** `docker compose down && docker compose up -d`
7. **Update clients:** `X-API-KEY` header in `claude_desktop_config.json` / n8n / REST clients.

Verify: `curl -X POST https://strike-tips-hud.vercel.app/api/agent/kill` → `401`, `curl -H "Origin: https://evil.com" https://striketips-mcp.../api/health -I` → `allow-origin: https://strike-tips-hud.vercel.app`.
EOF
