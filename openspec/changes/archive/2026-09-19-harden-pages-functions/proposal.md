## Why

September's recon left four verified edge findings open. Re-verified against the
post-`restore-hud-write-path` code on 2026-09-19:

1. **P2 — `POST /api/tasks` (exact path) still forwards anonymously.** The
   `matches()` helper is now slash-safe, but the hole moved into the data:
   `WRITE_PREFIXES` declares `'/api/tasks/'` (trailing slash), and the backend's
   real route is the bare `/api/tasks`. `matches('/api/tasks', '/api/tasks/')`
   is false on both branches (exact ≠, and `startsWith('/api/tasks//')` ≠), so
   the family guard silently skips its own family's primary route.
2. **P3 — upstream failure escapes as Cloudflare error 1101.**
   `functions/api/[[catchall]].ts:170-172` rethrows on the primary leg when the
   origin is Modal; the browser gets a raw 1101 crash page instead of structured
   JSON. Bonus find: the worker-fallback fetch (line 175) has **no timeout** —
   the 25 s AbortController covers only the primary leg.
3. **C1/C2 — keyless AI surface has no ceiling.** `/api/live` (Gemini Live voice
   proxy) is limited to 5 upgrades/min/IP and 10-min sessions but allows
   unlimited *concurrent* sessions per IP and has no global cap; the stream
   relay forwards frames upstream unthrottled. `/api/chat` has good per-call
   caps (`max_tokens: 1500`, body 32 KB, 20/min/IP) but no global ceiling.
4. **No CSP on the HUD document** (`public/_headers` has COOP/COEP only) while
   the app renders LLM `react-markdown` output.
5. **Rate-limit Maps never evict** (4 stores across 3 files): under spoofed-IP
   load they grow without bound inside each isolate.
6. **Turnstile failure UX gap (witnessed live):** when the challenge errors
   (e.g. `600010`) the modal closes silently and the user sees only the final
   write failure — no retry affordance.

## What Changes

- `production-security` (MODIFIED): write-family prefix lists are normalized
  (canonical form, no trailing slash) so every declared family guards its exact
  path AND subpaths; in-memory limiter state is bounded by eviction.
- `api-resilience` (ADDED): the reverse proxy never leaks an unhandled
  rejection — upstream failure returns a structured JSON 502 envelope; the
  fallback leg carries the same timeout as the primary.
- `ai-spend-guard` (ADDED): concurrent + global ceilings for `/api/live`,
  global ceiling + pinned existing caps for `/api/chat`, throttled frame relay.
- `edge-csp` (ADDED): Content-Security-Policy (Report-Only first) on HUD
  documents with Turnstile/LLM hosts allowlisted.
- `browser-write-auth` (MODIFIED): challenge failure/dismissal renders an
  explicit verification-failed state with a retry affordance.

## Capabilities

### Affected Specs
- `production-security` — MODIFIED (prefix completeness + bounded limiter state)
- `browser-write-auth` — MODIFIED (challenge-failure UX)
- `api-resilience` — ADDED
- `ai-spend-guard` — ADDED
- `edge-csp` — ADDED

## Non-Goals

- **No Modal/backend changes.** The asyncio-teardown churn and the
  bot-token-in-logs finding from the 2026-09-19 log review belong to a separate
  `modal-ops-hardening` change.
- **No polling-budget work** — that is `edge-poll-budget` (the ~25 req/min idle
  burn measured in the owner's own devtools trace on 2026-09-19).
- **No Durable Objects / KV-backed rate limiting.** Global caps stay
  isolate-local best-effort (documented honestly); a real distributed limiter
  is a future change if abuse appears.
- **No CSP enforcement flip** in this change — Report-Only first, with defined
  flip criteria.