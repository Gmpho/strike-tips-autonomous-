# Cloudflare MCP Edge — 3-Layer Architecture

> **Last Updated:** June 2026 | **Version:** 2.1

---

## Overview

The Cloudflare MCP Edge layer sits between the Vercel HUD frontend and the Modal backend, providing **always-free** compute for compute-light operations (OKF knowledge retrieval, Monte Carlo simulations, Kelly calculations, odds caching) while routing heavier AI/analysis workloads to Modal.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Vercel HUD (Vite + React)                     │
│                  https://strike-tips-hud.vercel.app                   │
│                          middleware.ts                                │
│              Routes /api/* /v1/* /mcp based on path                   │
└─────────────────┬───────────────────────────────────┬────────────────┘
                  │                                   │
                  ▼                                   ▼
┌──────────────────────────────┐    ┌──────────────────────────────────┐
│   Cloudflare Worker          │    │    Modal (serverless)            │
│   striketips-mcp             │    │    gmpho--strike-tips-racing     │
│   816 KiB / 160 KiB gzip     │    │    serve-api / run_odds_monitor  │
│   Always-free tier           │    │    ~$30/mo free credit           │
│                              │    │                                  │
│   ● 16 MCP tools             │    │    ● AI analysis (Gemini/Groq)  │
│   ● 8 REST endpoints         │    │    ● Telegram bot               │
│   ● OKF knowledge bundle     │    │    ● Dream engine simulations   │
│   ● D1 database (form)       │    │    ● Odds processing (fallback) │
│   ● KV cache (odds)          │    │    ● ChromaDB memory            │
└──────────────────────────────┘    └──────────────────────────────────┘
```

---

## Layers

### Layer 1: Cloudflare Worker (striketips-mcp)

**Deployed at:** `https://striketips-mcp.gmphorg379.workers.dev`

A Cloudflare Workers script (564 lines TypeScript) that provides both REST API and MCP protocol endpoints. Uses dual-mode: standard HTTP REST for HUD/frontend consumption and JSON-RPC 2.0 over HTTP for MCP client integration.

**Key specifications:**
- Runtime: Cloudflare Workers (nodejs_compat)
- SDK: `@modelcontextprotocol/sdk` v1.29.0
- Transport: `WebStandardStreamableHTTPServerTransport` (stateless)
- Auth: Optional `x-api-key` header
- Version: 2.0.0

### Layer 2: Vercel HUD Middleware

**Deployed at:** `https://strike-tips-hud.vercel.app`

The `middleware.ts` file acts as a single routing point. Requests are classified into two buckets:

| Bucket | Route To | Endpoints |
|--------|----------|-----------|
| **Cloudflare** | `striketips-mcp.gmphorg379.workers.dev` | `/api/health`, `/api/edge`, `/api/kelly`, `/api/circuit`, `/api/bayesian`, `/api/keywords`, `/api/evaluate`, `/api/verify-card`, `/api/patch-html`, `/api/racing/form`, `/api/racing/odds`, `/api/knowledge`, `/mcp` |
| **Modal** | `gmpho--strike-tips-racing-serve-api.modal.run` | Everything else (`/api/agent`, `/api/betting`, `/v1/*`) |

### Layer 3: Modal Backend (serve-api)

**Deployed at:** `gmpho--strike-tips-racing-serve-api.modal.run`

Modal handles all heavyweight compute: AI analysis, Telegram bot logic, dream engine, ChromaDB access, and PDF processing. Configured with `min_containers=0` to scale to zero when idle, saving costs.

---

## OKF Knowledge Bundle

### What It Is

The **OKF (On-Device Knowledge Framework)** bundle is a set of 12 curated markdown files covering South African horse racing knowledge. Each file has YAML frontmatter (title, description, tags, timestamp) and markdown body content.

### File Structure

```
knowledge/racing/
├── index.md                              # Bundle root: purpose, structure, usage
├── conditions/
│   └── going.md                          # Going & track conditions explained
├── strategies/
│   ├── kelly-criterion.md                # Optimal bet sizing math
│   └── value-betting.md                  # Value betting & merit ratings
└── tracks/
    ├── index.md                          # Track overview index
    ├── durbanville.md                    # Durbanville (1922, Cape Town)
    ├── fairview.md                       # Fairview (1977, Gqeberha)
    ├── greyville.md                      # Greyville (1844, Durban)
    ├── kenilworth.md                     # Hollywoodbets Kenilworth (1881, Cape Town)
    ├── scottsville.md                    # Scottsville (1886, Pietermaritzburg)
    ├── turffontein.md                    # Turffontein (1887, Johannesburg)
    └── vaal.md                           # Vaal (1946, Gauteng)
```

### Build Process

A build script (`scripts/build-knowledge.js`) converts the markdown files into a TypeScript module at build time:

```
knowledge/racing/*.md
        │
        ▼
scripts/build-knowledge.js   ← traverses recursively, parses YAML frontmatter
        │
        ▼
src/generated/racing-knowledge.ts   ← compiled TypeScript (34 KB, 12 entries)
```

The generated file exports:
- `racingKnowledge` — `Record<string, KnowledgeEntry>` map
- `searchKnowledge(query)` — ranked search (10× title/tags, 5× body, + per-occurrence)
- `getKnowledge(path)` — exact path lookup
- `getTrackKnowledge(name)` — partial name match
- `listKnowledgePaths()` — full path list
- `listTrackPaths()` — tracks-only path list

The build runs automatically via `predeploy` script before `wrangler deploy`.

### Track Data

Each track entry contains verified real data from web research:

| Track | Founded | Location | Notable |
|-------|---------|----------|---------|
| Hollywoodbets Kenilworth | 1881 | Cape Town (Western Cape) | New/old courses, 2800m/2700m |
| Durbanville | 1922 | Cape Town (Western Cape) | Left-handed turf, undulating |
| Fairview | 1977 | Gqeberha (Eastern Cape) | Polytrack + turf, 1900m |
| Turffontein | 1887 | Johannesburg (Gauteng) | Steepest climb in SA, Triple Crown venue |
| Vaal | 1946 | Gauteng | 1600m straight, turn track; CLASSICS |
| Scottsville | 1886 | Pietermaritzburg (KZN) | 1950m, undulating |
| Greyville | 1844 | Durban (KZN) | Pear-shaped, gradient sections |

### Search Scoring

The search ranks results by:
1. Index keyword match (tags + title + description + path): **+10 points**
2. First body occurrence: **+5 points**
3. Each additional body occurrence: **+1 point**

Example: `searchKnowledge("value betting")` returns 2 results ranked by relevance.

---

## REST Endpoints

All endpoints are served from the Cloudflare Worker at `/api/*`:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/health` | GET | Health check |
| `/api/edge` | GET | Edge calculation |
| `/api/kelly` | GET | Kelly criterion |
| `/api/circuit` | GET | Circuit breaker check |
| `/api/bayesian` | GET | Bayesian calibration |
| `/api/keywords` | GET | Keyword scanning |
| `/api/evaluate` | GET | Race evaluation |
| `/api/verify-card` | GET | Race card verification |
| `/api/patch-html` | GET | HTML patch |
| `/api/racing/form` | GET | Form insights (D1) |
| `/api/racing/odds` | GET | Odds (KV) |
| `/api/racing/evaluate/:track/:race` | GET | Evaluate specific race |
| `/api/knowledge` | GET | List all knowledge paths (12 total) |
| `/api/knowledge/search?q=` | GET | Search knowledge bundle |
| `/api/knowledge/tracks[?track=]` | GET | List/get track knowledge |
| `/api/ingest-snapshot` | POST | Ingest odds snapshot (from odds monitor) |
| `/api/ingest-insight` | POST | Ingest form insight (D1) |

---

## MCP Tools

The Worker registers 16 MCP tools accessible at `/mcp` via JSON-RPC 2.0:

### Original Tools (11)

| Tool | Description |
|------|-------------|
| `calculate_probability_edge` | Compute mathematical edge |
| `calculate_max_position` | Half-Kelly stake capped at 5% |
| `check_circuit_breakers` | Enforce 20% daily / 50% drawdown |
| `run_bayesian_calibration` | Beta-binomial prior update |
| `scan_semantic_keywords` | Extract racing keywords from text |
| `evaluate_race_matrix` | Get evaluation status |
| `verify_race_card_array` | Sanity-check runner count |
| `trigger_tab_html_patch` | Self-healing CSS selector patch |
| `search_past_races` | Search D1 form insights |
| `get_dream_simulation` | Dream engine simulation (via Modal) |
| `fetch_live_odds_stream` | Cached odds from KV |

### OKF Tools (4)

| Tool | Description |
|------|-------------|
| `search_racing_knowledge` | Search knowledge bundle by query |
| `list_racing_knowledge` | List paths, filterable by category |
| `get_racing_knowledge` | Get full entry by path |
| `get_track_knowledge` | Get track by partial name match |

### Web Search Tool (1)

| Tool | Description |
|------|-------------|
| `web_search_racing` | Web search (requires `SEARCH_API_KEY` secret) |

MCP protocol requires:
- `POST` to `/mcp`
- Header `Accept: application/json, text/event-stream`
- Optional auth via `x-api-key`

---

## Data Layer

### D1 Database (`strike-tips-racing`)

Relational database for form insights:
- Table: `form_insights` (doc_id, horse, content, type, track, race_number, date, metadata_json, created_at)
- 244 seeded form insights
- Parameterized queries with LIKE escaping

### KV Namespace (`ODDS_KV`)

Key-value cache for live odds:
- Key format: `odds:{track}:{race_number}`
- Full snapshot: `odds:full_snapshot`
- TTL: 300 seconds (5 minutes)
- Populated by Docker odds-monitor via `POST /api/ingest-snapshot`

### Odds Monitor → Cloudflare Push Flow

```
Docker odds-monitor
  (adaptive_odds_monitor.py)
        │
        ▼  httpx POST
  POST /api/ingest-snapshot
        │
        ▼
  Cloudflare Worker
        │
        ├── KV.put("odds:full_snapshot", snapshot)   (T+300s)
        └── KV.put("odds:{track}:{race}", event)      (per-event, T+300s)
```

---

## Deployment

### Cloudflare Worker

```bash
cd cloudflare_mcp_edge

# Build knowledge bundle
node scripts/build-knowledge.js

# Deploy (runs predeploy → build → wrangler deploy)
npm run deploy

# Set secrets
npx wrangler secret put BACKEND_API_URL
npx wrangler secret put BACKEND_API_KEY
npx wrangler secret put SEARCH_API_KEY   # optional, for web search
```

### Vercel HUD

```bash
cd strike-tips-hud

# Preview deploy
vercel

# Production deploy
vercel --prod

# Force fresh build (no cache)
vercel deploy --prod -y --force
```

A fresh build requires `--force` flag to skip Vercel's build cache.

---

## Environment Variables

### Cloudflare Worker Secrets

| Secret | Required | Description |
|--------|----------|-------------|
| `BACKEND_API_URL` | Yes | Modal backend URL |
| `BACKEND_API_KEY` | Yes | Shared API key for Modal auth |
| `SEARCH_API_KEY` | No | Brave Search API key for `web_search_racing` |

### Vercel HUD

| Variable | Description |
|----------|-------------|
| `STRIKE_TIPS_API_KEY` | Shared API key, passed to middleware as `x-api-key` |

---

## Key Decisions

1. **Stateless MCP Transport**: `sessionIdGenerator: undefined` in `WebStandardStreamableHTTPServerTransport` — fresh transport per HTTP request for Cloudflare Workers compatibility.

2. **OKF Compiled at Build Time**: Workers have no filesystem — markdown is converted to TypeScript via `scripts/build-knowledge.js` and bundled into the worker. Zero runtime fetch overhead.

3. **Middleware as Single Routing Point**: The Vercel `middleware.ts` replaces API rewrites in `vercel.json`, providing clear routing: Cloudflare for compute-light operations, Modal for heavy workloads.

4. **Docker Odds Monitor → Cloudflare KV**: Odds monitor runs locally, pushes snapshots to Cloudflare KV. Modal's `run_odds_monitor` is the fallback with `min_containers=0`.

5. **Real Track Data**: All knowledge files use verified facts from web research rather than placeholder content.

---

*Last Updated: June 28, 2026*
*Architecture Version: 2.1*
