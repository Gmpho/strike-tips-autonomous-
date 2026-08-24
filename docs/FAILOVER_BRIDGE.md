# 🔌 Failover Bridge — Surviving the Modal Credit Gap (Aug–Sep 2026)

How Strike Tips stayed live while Modal credits were exhausted (Aug 23 → Sep 1, 2026), the attempted Cloud Run migration, and the reconciliation plan for when Modal returns.

---

## TL;DR

| Question | Answer |
|---|---|
| Is production down during the gap? | **No** — HUD fails over to a Cloudflare tunnel → local Docker backend |
| Is real data lost? | **No** — Modal Volume `strike-tips-data` + ChromaDB Cloud both persist independently of running containers |
| What's the fallback chain? | `Modal (primary) → Cloudflare tunnel → local Docker` |
| What happens Sept 1? | Middleware auto-prefers Modal again → volume data reappears. Reconcile fallback-window bets (see below) |

---

## 1. The Failover Architecture

```
                       ┌── primary ──►  Modal serve-api
Vercel HUD (middleware)│                  (dark during credit gap)
                       │
                       └── fallback ─►  Cloudflare tunnel (trycloudflare.com)
                                           │
                                           ▼
                                        Local Docker (strike-bot-new :8000)
                                           │  bind-mounts repo data/
                                           ▼
                                        Live Betway/ATR scrapers (odds-monitor-new)
```

### HUD middleware (`strike-tips-hud/middleware.ts`)
- Proxies every `/api/*` + `/v1/*` request, **validating origins with a real `GET /api/system/health` probe** (3s timeout) before trusting them.
- **Critical lesson:** a suspended Modal function answers `404` *quickly* — a naive "got a response = healthy" check treats that as alive and never fails over. Only a `200` health response counts.
- Healthy origin cached for 60s; on failure the fallback origin (`BACKEND_FALLBACK_ORIGIN` env var) is probed next.

### HUD data bridge (`src/engine/data-bridge.ts`)
- SSE (`/api/monitoring/stream`) connects **directly** to a backend origin (bypasses Vercel Edge's ~300s runtime cap). Origins are probed in priority order at connect time:
  1. `''` (same-origin) — **dev only**: the Vite proxy routes to `127.0.0.1:8000`
  2. Modal
  3. `VITE_SSE_FALLBACK_ORIGIN` (tunnel / Cloud Run)
- Dark origins are **negative-cached for 60s** so reconnects don't stall 4s re-probing a dead Modal each time.
- REST hydration (`/api/news`, `/api/telemetry`) goes through relative paths — Vercel middleware in prod, Vite proxy in dev.

### Vercel env vars (Production)
| Var | Value | Feeds |
|---|---|---|
| `BACKEND_FALLBACK_ORIGIN` | tunnel URL | `middleware.ts` API failover |
| `VITE_SSE_FALLBACK_ORIGIN` | tunnel URL | `data-bridge.ts` SSE failover (baked at build) |

---

## 2. The Cloudflare Tunnel Bridge

Local Docker (`strike-bot-new` + `odds-monitor-new`) already scrapes Betway/ATR and serves the identical FastAPI on `127.0.0.1:8000`. A Cloudflare quick tunnel exposes it publicly:

```bash
# binary at ~/.local/bin/cloudflared
setsid nohup ~/.local/bin/cloudflared tunnel --url http://127.0.0.1:8000 --no-autoupdate &
```

**Backend CORS**: quick-tunnel hostnames rotate, so the backend allow-list uses a regex instead of fixed origins (`core_agent/api_pkg/__init__.py`):
```python
allow_origin_regex=r"https://[a-z0-9-]+\.trycloudflare\.com"
```

**Known limitation**: quick-tunnel URLs **rotate on every tunnel restart** → the Vercel env vars go stale. Mitigations, in order of durability:
1. Supervisor loop auto-restarts `cloudflared` (current setup — restarts are rare but rotate the URL)
2. **Named tunnel** — permanent URL, free, requires any domain in your Cloudflare account (~$10/yr) ← *recommended upgrade*
3. **Cloud Run** — permanent URL, no home-machine dependency ← *blocked on billing, see below*

---

## 3. The Cloud Run Attempt (blocked — resume here)

Goal: deploy `core_agent/`'s FastAPI to Cloud Run as a permanent always-on companion/fallback. **Everything is prepared; only GCP billing blocks it.**

### Done ✅
- `deploy-cloud-run.sh` (repo root) — one command: enables APIs, builds from the repo Dockerfile via Cloud Build, sets env vars from `.env`, deploys with SSE-compatible settings (`--timeout 3600`)
- HUD failover wired (above) — setting `BACKEND_FALLBACK_ORIGIN` to the Cloud Run URL is all that remains
- gcloud CLI installed (apt version — **not snap**; the snap build's OAuth is broken)

### Blocked ❌
- **Billing**: the account's only billing profile is closed; creating a new one failed with `OR_BACR2_44` (Google payments rejection — sometimes transient, worth retrying). Cloud Run requires an open billing account even for free-tier usage.

### Resume checklist (when billing clears)
```bash
gcloud auth login && gcloud auth application-default login
gcloud config set project strike-tips-16400
gcloud billing projects link strike-tips-16400 --billing-account=<ACCOUNT_ID>
./deploy-cloud-run.sh strike-tips-16400          # MIN_INSTANCES=1 for 24/7 background loops
# then: point both Vercel env vars at the run.app URL and redeploy
```
**Terraform: not needed** — gcloud + Cloud Build covers a single service. Revisit only if adding Memorystore/schedulers/IAM.

### Cloud Run design notes
- Redis features degrade gracefully without `REDIS_URL` (all call sites try/except); point at Upstash free tier for full pubsub
- ChromaDB: set the existing `CHROMA_HOST/API_KEY` env vars for cloud mode (ephemeral local disk otherwise)
- Background loops (odds monitor / swarm researcher / heartbeat) need `--min-instances=1` + always-on CPU (~$10–15/mo); `MIN_INSTANCES=0` = free tier but loops pause at scale-to-zero
- Telegram webhook must be re-registered to the new URL during any cutover

---

## 4. Data Divergence — read before betting during the gap

Two **diverged copies** of state now exist:

| Copy | Location | Contents |
|---|---|---|
| **Canonical** | Modal Volume `strike-tips-data` | All production bet history, bankroll progression, snapshots (Aug 20 → gap start) |
| **Fallback** | repo `data/` (bind-mounted into local Docker) | Local-era state; any bets placed via HUD during the tunnel window land **here** |
| **Memories/chats/dreams** | ChromaDB **Cloud** | Single shared copy — never diverged |

- **Nothing was lost.** Modal Volumes persist independently of running containers; credits stopping ≠ data deletion.
- When Modal returns, middleware auto-prefers it → the canonical volume data reappears untouched.
- **Caveat**: bets placed through the HUD during the tunnel window exist only in the local copy. Before/after switching back, reconcile:
  ```bash
  # adapt scripts/sync_data_to_modal.py, or push specific files:
  modal volume put strike-tips-data data/bet_history.json /bet_history.json
  ```

---

## 5. Sept 1 — Modal Return Checklist

1. Confirm credits restored: `modal app list` / dashboard
2. `modal deploy -m core_agent.core.modal_app`
3. Smoke test: `curl https://gmpho--strike-tips-racing-serve-api.modal.run/api/system/health` → expect `200 HEALTHY` (not 404)
4. Verify volume data: check bankroll/bet history via HUD Analytics (should show the pre-gap history)
5. **Reconcile** any fallback-window bets (local `data/` → Modal volume, section 4)
6. HUD auto-reverts to Modal (middleware priority) — optionally remove the tunnel env vars, or keep them as permanent failover
7. Re-register the Telegram webhook to the Modal URL if it was moved

---

*Created: Aug 23, 2026 · v10.3 PRO / sw v2.5.0*
