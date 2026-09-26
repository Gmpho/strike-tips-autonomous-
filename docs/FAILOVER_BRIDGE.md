# 🔌 Backend Architecture & Failover Guide

How the HUD routes API traffic, which origin is primary, and how to opt into an
optional self-hosted fallback (e.g. Cloud Run) when needed.

> **Primary is always Modal.** An optional fallback origin is only used when you
> explicitly set an environment variable — nothing is hard-coded, and there is
> no Cloudflare *tunnel* in the active routing anymore.

---

## TL;DR

| Question | Answer |
|---|---|
| What is the primary backend? | Modal (`serve-api`) |
| What is the Cloudflare Worker? | An always-on edge layer for a fixed set of cheap read endpoints (MCP). Kept. |
| Is there a fallback? | Optional — only if `BACKEND_FALLBACK_ORIGIN` is set (e.g. your Cloud Run URL). |
| Is a Cloudflare quick-tunnel used? | **No** — removed from the active code path. |
| Nothing hard-coded? | Correct — fallback URL comes from env vars; docs use placeholders. |

---

## Architecture

```
                         ┌── primary ──►  Modal serve-api (FastAPI + scrapers)
Vercel HUD (middleware)  │
                         └── edge ─────►  Cloudflare Worker (read/MCP endpoints)
                         └── optional ──►  <YOUR_FALLBACK_URL>  (only when set)
```

### HUD middleware (`strike-tips-hud/middleware.ts`)
- **Modal is primary** — listed first, wins whenever healthy.
- Routes a fixed set of endpoints to the **Cloudflare Worker** (read/MCP), the
  rest go to the backend.
- Options are **validated with a real `GET /api/system/health` probe** (3s
  timeout) — a suspended Modal answers `404` fast, which a naive check mistakes
  for healthy. Only a `200` health response counts.
- Optional fallback via `BACKEND_FALLBACK_ORIGIN` env var (e.g. your Cloud Run
  URL). Leave unset to run Modal-only.

### HUD data bridge (`src/engine/data-bridge.ts`)
- SSE (`/api/monitoring/stream`) connects **directly** to a backend origin
  (bypasses Vercel Edge's ~300s runtime cap). Origins are probed at connect time:
  1. `''` (same-origin) — **dev only** (Vite proxy routes to `127.0.0.1:8000`)
  2. Modal
  3. `VITE_SSE_FALLBACK_ORIGIN` — **optional**, set to a fallback (e.g. Cloud Run)
- Dark origins are **negative-cached for 60s** so reconnects don't stall.
- REST hydration (`/api/news`, `/api/telemetry`) goes through relative paths —
  Vercel middleware in prod, Vite proxy in dev.

### Vercel env vars (Production)
| Var | Value | Feeds |
|---|---|---|
| `BACKEND_FALLBACK_ORIGIN` *(optional)* | `<YOUR_FALLBACK_URL>` | `middleware.ts` fallback |
| `VITE_SSE_FALLBACK_ORIGIN` *(optional)* | `<YOUR_FALLBACK_URL>` | `data-bridge.ts` SSE fallback |

> Leave both unset to run **Modal-only**. The URLs are never hard-coded — put
> your own origin (e.g. a Cloud Run URL) in Vercel env vars when you opt in.

---

## Option A: Modal-only (default)

No extra config. Middleware routes the read/MCP set to the Cloudflare Worker and
everything else to Modal. Nothing else to run.

## Option B: Opt-in fallback (e.g. Cloud Run)

When you want an always-on companion so the app keeps serving during a Modal
outage, point the fallback at a self-hosted origin:

1. Deploy your FastAPI to a fallback host (see `deploy-cloud-run.sh` for Cloud
   Run) and get a stable URL like `<YOUR_FALLBACK_URL>`.
2. In Vercel Project Settings → Environment Variables, set:
   - `BACKEND_FALLBACK_ORIGIN` = `<YOUR_FALLBACK_URL>`
   - `VITE_SSE_FALLBACK_ORIGIN` = `<YOUR_FALLBACK_URL>`
3. Redeploy the HUD. Modal stays primary; the fallback is only contacted if the
   health probe fails on Modal.

**Cloud Run notes** (from `deploy-cloud-run.sh`):
- `MIN_INSTANCES=1` keeps background loops (odds monitor / swarm researcher /
  heartbeat) alive (~$10-15/mo); `MIN_INSTANCES=0` = scale-to-zero free tier.
- Re-register the Telegram webhook to the fallback URL during any cutover.
- Redis/ChromaDB degrade gracefully without dedicated cloud services.

---

## Data resilience

- **Modal volumes (`strike-tips-data`) and ChromaDB Cloud persist independently
  of running containers** — downtime ≠ data loss.
- When Modal returns healthy, middleware auto-prefers it again automatically.

---

*Documented for the active codebase — no hard-coded fallback URLs.*
