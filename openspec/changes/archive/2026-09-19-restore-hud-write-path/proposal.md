## Why

Production is currently broken in a way the monitoring cannot see, because reads
all work. Verified live against `https://strike-tips-hud.pages.dev` on 2026-09-19
(canary paths + an in-page `fetch` stub, zero production mutations):

- `POST /api/config`, `POST /api/config/test_telegram`, `POST /api/healing/pulse`
  all return `401 {"error":"Unauthorized"}` — the Pages Function guard, not Modal
  (Modal's body differs: `{"detail":"Unauthorized: ..."}`). The browser holds no
  key anywhere in `src/`, and the guard demands the caller's `x-api-key` equal the
  master secret for every write family.
- The emergency stop is dead **and deceptive**: `AgentStatus.tsx` runs
  `await apiFetch(endpoint); setIsLocked(!isLocked)` with no status check, so the
  HUD displays red "Agent locked" while `brain.set_emergency_stop(True)` was never
  called (proven: label flipped `"Lock agent pipeline"` → `"Unlock agent pipeline"`
  on a 401 with no network call leaving the browser).
- Console is clean — the failures are silent by construction.

The guard was the September confused-deputy fix and its intent is correct; its
design is incomplete. There is no legitimate browser credential path at all, so
the fix must *add* one, never remove the guard. Approved design: **option B** —
a Turnstile-gated, short-lived signed browser session token minted at the edge,
accepted as proof-of-browser for legitimate writes, while
`/api/agent/{kill,reset}` stay master-key-only.

## What Changes

- New `strike-tips-hud/functions/_middleware.ts`: mints and verifies a signed
  browser session token (Turnstile gate, short lifetime, replay protection).
  The master secret never leaves the server boundary.
- `functions/api/[[catchall]].ts`: accepts the session token as proof-of-browser
  for legitimate write families (`/api/config*`, `/api/healing/*`,
  `/api/dreaming/*`); `kill`/`reset` and other master-key-only actions are
  unchanged and can never be satisfied by a session token.
- `AgentStatus.tsx`: verifies `res.ok` and reads back true engine state before
  flipping the lock UI; surfaces failures instead of flipping optimistically.
- `SettingsView.tsx` and `HealingView.tsx`: surface write errors to the user
  (currently silent on failure).
- Reads are untouched: keyless direct-origin fast path, zero quota impact.
- No backend changes, no money-path changes, no secret rotation required.

## Capabilities

### New Capabilities

- `browser-write-auth`: contract for the edge-minted proof-of-browser session
  token — issuance rules, acceptance rules, scope boundaries, and the HUD's
  obligation to verify write responses before reflecting state.

### Modified Capabilities

- `production-security`: the "Middleware rate limiting and sensitive-path auth"
  requirement gains the session-token acceptance rule for legitimate writes and
  the explicit guarantee that a session token can never satisfy
  `/api/agent/{kill,reset}`. Full updated requirement text is included in the delta.

## Impact

- **Edge (behavioral):** `strike-tips-hud/functions/_middleware.ts` (new),
  `strike-tips-hud/functions/api/[[catchall]].ts` (token acceptance branch),
  shared rate-limit module if one already exists from the sibling change.
- **HUD:** `src/components/sidebar/AgentStatus.tsx` (verify-then-flip +
  state read-back), `src/components/sidebar/SettingsView.tsx` and
  `HealingView.tsx` (error surfacing).
- **Secrets:** Turnstile site/secret keys added to Pages env; master key stays
  server-side only. No rotation of existing secrets required.
- **Risk:** a new token mechanism must be correct (minting, expiry, replay
  protection); the sensitive-path guarantee must be proven by a decision-table
  test that asserts a session token on `/api/agent/kill` returns 401. Backend,
  settlement, staking and all reads are untouched.