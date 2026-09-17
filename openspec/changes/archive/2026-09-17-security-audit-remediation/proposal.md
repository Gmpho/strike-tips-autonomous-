## Why

Sep-2026 external audit (red-team, reviewed line-by-line against live code, not trusted blindly) found two live holes: unauthenticated `/v1/*` LLM inference (Denial of Wallet) and confused-deputy key injection on write paths. Plus a PIN brute-force gap and a Chroma query bug burning Groq calls. Two audit claims were corrected during review (stale middleware.ts target, already-gated `/agent/memory`).

## What Changes

* `security.py`: fail-closed auth extended to `/v1/*` + `/ws/chat` (key via header, Bearer, or WS query); SAFE_PATHS untouched; missing server key denies all.
* Pages api Function: state-changing families (betting/config/healing/tasks/agent-kill) require caller key; writes capped 20/min/IP; reads unchanged.
* Pages v1 Function: 30/min/IP cap on the LLM path.
* Chroma freshness gate: `$and` filter (was throwing on every cycle, silently rebuilding insights + burning Groq).
* Telegram PIN: 5 fails → 30-min lockout, volume-shared across containers, fail-open on I/O.
* Deferred (needs custom domain): Cloudflare WAF rate-limit rules — impossible on pages.dev/workers.dev.

## Capabilities

### New Capabilities
- `security-hardening`: auth perimeter, proxy least-privilege, PIN lockout.

### Modified Capabilities
- `production-security`: /v1 + WS now keyed; proxy write auth.
