## Context

Traffic flows browser → Vercel middleware (injects `X-API-KEY` from server
env, forwards to Modal or Cloudflare) and browser → Cloudflare Worker
directly for MCP/knowledge/odds paths. Modal's FastAPI layer already
enforces `X-API-KEY` except `SAFE_PATHS`. The gaps were all at the two
edges: middleware forwarded blindly, worker authorized vacuously.

## Goals / Non-Goals

**Goals:**
- No unauthenticated state-changing or data-reading access.
- Free-tier DoS resistance via cheap in-memory rate limiting.
- Rotation that is boring, documented, and verifiable with curl.

**Non-Goals:**
- User identity / sessions / per-user quotas (single-operator system; a
  shared service key matches the threat model).
- WAF rules or Cloudflare paid features (always-free tier constraint).

## Decisions

- **Header-key auth, fail-closed**: matches the existing `x-api-key`
  convention between middleware, worker, and Modal; no new credential types.
  Sensitive-path list is explicit and tiny (kill/reset) so read endpoints
  stay frictionless for the HUD's polling.
- **In-memory fixed window** for rate limiting: no new infra (Redis/KV),
  sufficient at 100/min/IP; counters reset on edge-instance recycle, which
  only errs toward leniency.
- **Origin allowlist over regex**: exact-match set is auditable; localhost
  entries keep dev working without code switches.
- **Docs over automation for rotation**: four stores across three vendors;
  a runbook with copy-paste commands beats a brittle script.

## Risks / Trade-offs

- Shared key means rotation revokes all clients at once (Telegram, HUD,
  scripts) — acceptable for a single operator; rotation runbook covers it.
- In-memory limits don't coordinate across edge instances — worst case is
  under-enforcement, never lockout.
- `SAFE_PATHS` on Modal (health/SSE/docs) stay public by design; SSE carries
  market data the HUD needs without headers (EventSource limitation).
