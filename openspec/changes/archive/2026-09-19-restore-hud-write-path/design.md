## Context

Facts established by the 2026-09-19 live investigation (HTTP probes, an
in-page fetch stub, zero production mutations):

- The Pages Function `[[catchall]].ts:86-99` classifies `/api/config*`,
  `/api/healing/*`, `/api/betting/*`, `/api/tasks/`, `/api/agent/kill|reset` as
  writes and demands the *caller* present `x-api-key` equal to the master
  secret. The browser never holds a key (grep of `src/` is empty), so every one
  of these HUD actions 401s: settings save, "Test Telegram", healing pulse,
  emergency stop/reset.
- Unaffected paths prove the guard is selective, not a blanket outage:
  `GET /api/config` → 200, `POST /api/dreaming/pulse` → 200 (not a write
  prefix), `POST /api/chat` → 400 on empty body (dedicated function), `POST /api/tts`
  → 422 from Modal (catchall, not a write prefix).
- `AgentStatus.tsx:12-14` flips its lock UI unconditionally after the call.
- Reads go through two mechanisms that must not be disturbed: dedicated edge
  Functions and `directBackendUrl` keyless reads to the origins.
- Cloudflare Pages supports a global `functions/_middleware.ts` (currently
  absent), which is the natural issuance point for a browser-scoped credential.

## Goals / Non-Goals

**Goals:**

- Restore the HUD's legitimate writes in production without weakening the
  confused-deputy protection: anonymous actors gain nothing new, the browser
  gains an attributable credential.
- Make the emergency stop truthful: UI state always reflects a verified server
  response, never an optimistic flip.
- Give the later global spend budget an attributable unit (the session) to
  count against.

**Non-Goals:**

- Not a rewrite of the guard's decision table beyond adding the token branch;
  rate limits, `WRITE_PREFIXES` and `SENSITIVE_PREFIXES` keep their current
  semantics.
- No backend change, no Modal route change, no money-path change, no rotation
  of the master secret.
- Not bot-detection perfection: Turnstile is a friction gate against casual
  abuse and automation replay, not a proof of humanity. The spend-side budget
  (a sibling change) remains necessary.
- Not storing any token or key in `localStorage`/cookies beyond the
  short-lived session token itself (option C was considered and rejected —
  a master key in browser storage would turn HUD XSS into key theft).

## Decisions

1. **Session token minted in `functions/_middleware.ts`, verified in `[[catchall]].ts`.**
   A single module (`functions/lib/session.ts`) owns mint/verify so the two
   call sites cannot disagree. Alternatives rejected: minting inside `[[catchall]].ts`
   (only intercepts matched routes, not the whole surface) and validating in the
   HUD (client-side validation is not validation).
2. **Token is anonymous-but-attributable, never identity.** It proves "a real
   browser passed Turnstile within the last N minutes", not a user. Enough for
   settings/healing/dreaming writes; deliberately insufficient for kill/reset.
3. **Kill/reset remain master-key-only with an explicit negative test.** The
   decision table must contain a row asserting that a session token on
   `/api/agent/kill` returns 401. This is the regression that would silently
   undo September's fix.
4. **HUD verifies before reflecting state.** `AgentStatus` requires `res.ok`
   AND the response body's `status` to match the request (`locked`/`active` —
   the backend's own kill/reset responses already carry this) before
   flipping; any failure renders an error state instead. Settings and healing
   surfaces show write failures that are silent today. (Spec originally said
   "re-read engine state"; there is no GET exposing `emergency_stop`, so the
   in-band body confirmation replaces the second read — option 1, approved
   by the owner 2026-09-19. A `GET /api/agent/status` remains available as a
   future separate backend change if external verification is ever wanted.)
5. **Unit-test with Node's built-in `node:test`, zero new dependencies.** The
   guard logic is pure functions (mint/verify/match/decide) lifted into a
   shared module, matching the repo's "confirmed libraries only" rule.
6. **HUD bootstrap is the client half of requirement 1.** The task list
   originally omitted it; implementation surfaced the gap before any deploy.
   `src/lib/session-client.ts` fetches the public site key from the edge
   (`GET /api/session`), renders the Turnstile widget on demand (overlay, one
   inflight promise), POSTs `/api/session`, and session-scoped callers retry a
   write once on 401. **The site key is deliberately NOT read from build-time
   env**: with `VITE_TURNSTILE_SITE_KEY` unset, the bundler constant-folded
   the entire module to a 132-byte `return false` shim, so a deployed bundle
   could never mint a session even after the key was configured. Edge-serving
   the public key keeps the code live and makes key rotation rebuild-free.
   The secret never touches the client. Added scope approved by the owner
   2026-09-19.

## Risks / Trade-offs

- **Token theft/replay.** Mitigation: short TTL, single-audience binding,
  Turnstile gating issuance, and the scope ceiling (a stolen token can change
  settings or pulse a dream, never kill, reset, bet, or touch healing writes
  beyond pulse). The spend budget (sibling change) bounds volume.
- **Clock skew on expiry.** Mitigation: generous leeway window and a
  renewal path on the next user interaction rather than a hard wall.
- **`_middleware.ts` runs on every request.** Mitigation: issuance is
  lazy (only when no valid token is present) and verification is a cheap
  signature check; no upstream calls on the hot path.
- **Accidentally broadening the token's scope later.** Mitigation: the scope
  list is an allowlist in one module with the negative kill/reset test as the
  tripwire.
## Live-deployment debug log (2026-09-19, post-approval)

Production verification surfaced two failure modes no local gate could catch —
both reproduced, root-caused with control experiments, and fixed in prod:

| # | Symptom | Root cause | Control experiment | Fix |
|---|---|---|---|---|
| 1 | Human solved the challenge; retried write still 401 | fetches carried no explicit `credentials`, so the `HttpOnly` session cookie never attached to the retried write (webview defaults are unreliable) | anonymous `POST /api/session` + bad token → **403, zero `Set-Cookie`** — no cookie could ever exist to send | explicit `credentials: 'same-origin'` on `apiFetch` + both `session-client` fetches (`00ec8271`, client rebuild) |
| 2 | Same 401 after solve even with cookies fixed | middleware called `turnstile/v1/siteverify` — **a nonexistent path (404)**, so *every* verification failed | same request against **v0** → `200 {success:false, error-codes:['invalid-input-response']}` — secret valid, endpoint real | URL corrected to `turnstile/v0/siteverify` (`b89361d3`) + `error-codes` surfaced in the 403 body |

Post-fix prod proof through the real middleware: `POST /api/session` with a
dummy token → `403 {"error":"Challenge failed","codes":["invalid-input-response"]}`
— the full siteverify round-trip runs, the secret is accepted, bad tokens are
rejected. A headless-browser solve attempt is refused by Turnstile itself
(`600010`), independently confirming the challenge enforces.

**Residual gate:** one genuine human-solved challenge in a real browser. The
issuance requirement is met by mechanism and demonstrated end-to-end up to the
token exchange; the human click is the final input only Turnstile can adjudicate.
