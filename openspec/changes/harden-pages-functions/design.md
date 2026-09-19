## Context

Five edge files (`functions/api/[[catchall]].ts`, `_middleware.ts`,
`api/chat.ts`, `api/live.ts`, `public/_headers`) plus one client module
(`src/lib/session-client.ts`). Constraints: Pages free tier (no Durable
Objects used today), per-isolate memory, the Sep-2026 lesson that local test
stubs are blind to exactly the failures this change fixes — so every fix ships
with a harness row that exercises the real code path.

## Goals / Non-Goals

- Goals: close P2 at the data layer, never emit 1101, cap the keyless AI
  surface, bound limiter memory, make challenge failure actionable.
- Non-Goals: distributed rate limiting, backend changes, CSP enforcement.

## Decisions

1. **Prefix normalization at the data layer (P2).** Add `normalizePrefix()`
   (strip one trailing `/`) applied where the lists are *declared*; `matches()`
   stays exactly as the session change shipped it. Exact-path and subpath
   matching then both work for every family. Harness pins the fixed row:
   anonymous `POST /api/tasks` → 401.
2. **502 envelope, not rethrow (P3).** Catch on both legs; return
   `{ error, upstream, retryable: true }` as JSON 502 with `Retry-After: 5`.
   The worker-fallback leg gets the same 25 s AbortController as the primary.
   Success-path streaming is untouched (body passes through).
3. **Eviction in `hitRate` stores.** On a window rollover, delete expired
   entries for that store and enforce a hard key cap (oldest-expiry eviction).
   Cheap, allocation-light, keeps every isolate's maps bounded.
4. **Live spend ceiling (C1).** Per-IP concurrent sessions capped at 1
   (second WS upgrade → 429), global concurrent cap (isolate-local, 10) → 429,
   and the upstream relay drops client frames beyond a per-session message
   rate. The existing 10-min hard close stays.
5. **Chat global cap (C2).** Isolate-local global counter per window on top of
   the existing per-IP 20/min; per-call caps already verified (`max_tokens:
   1500`, 32 KB body) — pinned by harness, not changed.
6. **CSP Report-Only first.** `Content-Security-Policy-Report-Only` in
   `_headers`: `script-src 'self' https://challenges.cloudflare.com`,
   `frame-src https://challenges.cloudflare.com`, `connect-src 'self'
   https://generativelanguage.googleapis.com https://api.groq.com`,
   `style-src 'self' 'unsafe-inline'` (Three.js/Framer inline styles),
   `object-src 'none'`, `base-uri 'self'`. Enforcement flips after ≥7
   violation-free days — a documented criterion, not this change's scope.
7. **Challenge retry UX.** `session-client` keeps the widget mounted on
   `error-codes`/timeout/expired, surfaces `challenge-failed` to the caller,
   and resets the widget in place; `SettingsView` renders the explicit
   verification-failed state with a Retry button (no page reload).

## Risk / Trade-offs

- Global caps are per-isolate (best-effort). Honest limitation; the spec says
  so. A distributed limiter is deliberately out of scope.
- `style-src 'unsafe-inline'` is a pragmatic concession; tightening it is
  future work once the RO reports confirm nothing else breaks.
- Eviction sweeps only on window rollover (O(amortized)); a fully proactive
  sweeper adds isolate CPU for no benefit at this traffic.