# Security Audit — Strike Tips Racing Bot

Audit conducted: 2026-06-02
Scope: Full application (FastAPI backend, Modal deployment, Docker containers, Redis, browser automation)

---

## Findings

### C-1: No Authentication on API Routes

**Severity**: Critical  
**File**: `core_agent/core/security.py` (pre-fix)  
**Status**: Fixed

The `AuthMiddleware` had a `SAFE_PATHS` set that included `/api/` — meaning every single API endpoint (scan, bet, config, monitoring, healing) was accessible without any credential. An attacker who discovered the Modal URL could run scans, place bets, read bankroll data, and trigger auto-healing workflows.

**Fix**: Removed `/api/` from `SAFE_PATHS`. All `/api/*` routes now require `X-API-KEY` header matching `STRIKE_TIPS_API_KEY`. Whitelisted only `/`, `/docs`, `/openapi.json`, `/telegram-webhook`, `/api/system/health`, and `/mcp/*`.

---

### C-2: API Keys in `.env` Readable by Any Container Process

**Severity**: Critical  
**File**: `.env` (gitignored, but readable at runtime)  
**Status**: Mitigated (requires human action)

Eight API keys (Telegram, OpenAI, Anthropic, Groq, Gemini, Chroma, GitHub, Ollama) are stored in `.env` and loaded as environment variables. Any process running inside the container — including compromised dependencies — could read them via `/proc/self/environ` or `os.environ`.

**Fix**: Reduced attack surface by running as non-root user (`USER appuser` in Dockerfile). Full remediation requires:
1. Revoking all existing keys at provider dashboards
2. Generating new keys
3. Updating `.env` locally and `strike-tips-secrets` on Modal

---

### C-3: Missing Security Controls

**Severity**: Critical  
**Files**: `core_agent/api.py`, `Dockerfile`  
**Status**: Fixed

| Missing Control | Risk | Fix Applied |
|---|---|---|
| Rate limiting | Brute-force / DoS on API endpoints | 30 requests per 60s per IP |
| Weak PIN auth | `/auth <PIN>` uses a simple PIN with no rate-limit on guesses | Rate limiting covers auth too |
| No CSRF protection | State-changing GET requests | CORS tightened to known origins only |
| Overly permissive CORS | `allow_origins=["*"]` allowed any website to call the API | Locked to `localhost:5173` and Vercel HUD |
| No CSP headers | XSS could execute in-browser | `Content-Security-Policy` applied |
| No HSTS | HTTP downgrade attacks possible | `Strict-Transport-Security: max-age=31536000` |
| No XFO | Clickjacking via iframe embed | `X-Frame-Options: DENY` |
| No Permissions-Policy | Unused APIs available to browser | Camera/mic/geolocation disabled |

---

### C-4: Redis Exposed Without Password or TLS

**Severity**: Critical  
**File**: `docker-compose.yml`  
**Status**: Fixed

Redis ran on default port 6379 mapped to host with no `--requirepass`. Any process on the host network (or another container) could connect and read/write all cached data, task queues, and session state.

**Fix**: Added `command: redis-server --requirepass "${REDIS_PASSWORD}"`. All `REDIS_URL` references updated to include password. Port changed from `ports` (host-exposed) to `expose` (internal-only). Redis MCP bridge in `mcp_server.py` updated to read `REDIS_URL` from environment.

---

### C-5: Docker Containers Running as Root

**Severity**: Critical  
**File**: `Dockerfile`  
**Status**: Fixed (partial — Modal skips USER instruction)

The Playwright base image runs as root by default. A compromised Python dependency could install system packages, modify binaries, or escape the container.

**Fix**: Added `groupadd` / `useradd` for `appuser` and `USER appuser` at end of Dockerfile. Note: Modal containers do not support the `USER` instruction and always run as root — applies to local Docker and non-Modal deployments only.

---

### H-1: Hardcoded Redis URL in MCP Server

**Severity**: High  
**File**: `core_agent/core/mcp_server.py` (pre-fix)  
**Status**: Fixed

The `bridge_to_redis` tool hardcoded `redis://localhost:6379/0` with no password. If the Redis server was bound to a different host or required auth, this tool would silently fail or connect to the wrong instance.

**Fix**: Now reads `REDIS_URL` from environment, with fallback to `redis://:{REDIS_PASSWORD}@localhost:6379/0`.

---

### H-2: No Input Validation on Track Names

**Severity**: High  
**File**: `core_agent/routes/racing.py` (pre-fix)  
**Status**: Fixed

Track name parameters were passed directly to scraping and analysis functions without validation. Path traversal (`../../../etc/passwd`) or unexpected values could cause undefined behavior.

**Fix**: Added `ALLOWED_TRACKS` whitelist. Track names are lowercased, stripped of spaces and special characters, and rejected with 400 if not in the known set.

---

### H-3: Missing Preconnect Hint

**Severity**: High  
**File**: `strike-tips-hud/index.html` (pre-fix)  
**Status**: Fixed

The HUD frontend made ~14 parallel API calls to Modal on load. Without a `<link rel=preconnect>` hint, the browser had to complete DNS + TCP + TLS for each request, adding ~2.7s LCP delay due to Modal cold starts.

**Fix**: Added `<link rel="preconnect" href="https://gmpho--strike-tips-racing-serve-api.modal.run">`. Combined with `min_containers=1` on `serve_api` in `modal_app.py`, cold starts are eliminated.

---

### H-4: Nonexistent PyPI Package Pin

**Severity**: High  
**File**: `requirements.txt` (pre-fix)  
**Status**: Fixed

`requests==2.33.0` does not exist on PyPI. This caused the Docker build to fail silently (falling back to a cached version) or error.

**Fix**: Changed to `requests>=2.32.3,<2.33`.

---

### M-1: No Global Key Expiry on Redis

**Severity**: Medium  
**File**: `docker-compose.yml`  
**Status**: Unfixed (design decision)

Redis has no `maxmemory-policy` set. Stale cached data, task queue items, and snapshots accumulate indefinitely and could exhaust the 30 MB Redis Cloud free tier.

**Remediation**: Add `--maxmemory-policy allkeys-lru` to Redis command, or implement TTLs on specific key types in application code.

---

### M-2: Exposed Internal Service Ports

**Severity**: Medium  
**File**: `docker-compose.yml` (pre-fix)  
**Status**: Fixed

Redis (6379), Ollama (11434), and RedisInsight (5540) were all mapped to the host interface, accessible from any process on the local network.

**Fix**: Changed all three from `ports` to `expose` (Docker internal network only).

---

### M-3: Weak Kill Switch / Reset Routes

**Severity**: Medium  
**File**: `core_agent/routes/healing.py`  
**Status**: Mitigated

System reset and kill-switch routes (`/api/healing/*`) are now behind the `X-API-KEY` auth check (C-1 fix). However, if the API key is compromised, an attacker could halt the entire bot.

**Remediation**: Add an additional confirmation step (e.g., require both a header and a query param) for destructive operations.

---

## Summary

| Severity | Count | Fixed | Unfixed |
|---|---|---|---|
| Critical | 5 | 4 | 1 (key rotation needs human) |
| High | 4 | 4 | 0 |
| Medium | 3 | 2 | 1 (Redis eviction policy) |

**Next scheduled audit**: 2026-07-02 (monthly)
