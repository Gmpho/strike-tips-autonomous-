## 1. Proxy hardening (`functions/api/[[catchall]].ts`)

- [x] 1.1 Normalize `WRITE_PREFIXES`/`SESSION_WRITE_PREFIXES` at declaration (strip one trailing `/`) so `POST /api/tasks` exact is guarded; keep `matches()` untouched
- [x] 1.2 Wrap both upstream legs: JSON 502 envelope `{error, upstream, retryable}` + `Retry-After: 5` on rejection — no rethrow on the Modal leg
- [x] 1.3 Give the worker-fallback leg the same 25 s AbortController as the primary
- [x] 1.4 Bound `rateStore`/`writeStore`: evict expired on window rollover + hard key cap (oldest-expiry eviction) — via shared `functions/lib/rate-limit.ts`; middleware challenge store and live/chat stores bound too

## 2. AI spend guard

- [x] 2.1 `api/live.ts`: per-IP concurrent = 1, global concurrent cap (isolate-local), 429 on excess; release on `closeAll()`
- [x] 2.2 `api/live.ts`: throttle relayed client frames (drop beyond per-session rate) — `makeFrameThrottle()` token bucket, exported for tests
- [x] 2.3 `api/chat.ts`: global per-window ceiling isolate-wide on top of per-IP 20/min; per-call caps pinned as exported constants with a test

## 3. Security headers + challenge UX

- [x] 3.1 `public/_headers`: `Content-Security-Policy-Report-Only` (self + `challenges.cloudflare.com` for script/frame, LLM hosts in connect-src, inline styles, `object-src 'none'`)
- [x] 3.2 `session-client.ts`: keep widget mounted on error/expire/dismiss, surface `challenge-failed`, in-place reset + retry (overlay-level Retry/Cancel)
- [x] 3.3 `SettingsView.tsx` + `HealingView.tsx`: explicit verification-failed state with retry affordance (no reload)

## 4. Tests + verification

- [x] 4.1 Extend `tests/catchall.test.ts`: exact `/api/tasks` 401 (guarded now), 502 envelope on rejected upstream (fetch stubbed to throw), bounded-store unit case
- [x] 4.2 Extend tests: throttle refill/drop + per-call caps pinned (`tests/spend-guard.test.ts`)
- [ ] 4.3 Local proof via `wrangler pages dev` (`/api/session`, tasks 401, 502 envelope), then deploy and canary prod (tasks 401 live, reads unregressed, RO header present); full suite green + `openspec validate --all`

## Verification

- `node --test tests/` all green; `npx tsc --noEmit` clean; production build clean
- `openspec validate harden-pages-functions` valid; `--all` green
- Live: `POST /api/tasks` anonymous → 401; killed-origin probe → JSON 502 (not 1101); `_headers` carries Report-Only CSP