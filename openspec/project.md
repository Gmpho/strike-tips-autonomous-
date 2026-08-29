# Project: Kimi Agent Strike Tips Racing Bot

## Purpose

South African Horse Racing Intelligence System — God Mode betting assistant that identifies **value bets** (mathematical edge, not tips) across South African tracks plus global coverage (USA, Japan, Hong Kong, Australia, etc.) via Betway. Provides disciplined staking, Bayesian learning, and real-time HUD.

Core promise: **Probability edge analysis + Half-Kelly staking with hard guards** (5% max per bet, 20% daily loss halt, DSI scaling) — not "hot tips".

## Tech Stack

**Languages:** Python 3.9+ (backend), TypeScript (frontend/worker)

**Backend — `core_agent/` (Modal serverless + Docker):**
- FastAPI + Pydantic, `httpx`, `asyncio`
- Scrapers: `Scrapling` (StealthyFetcher/Fetcher), `Playwright` (odds-monitor)
- AI: Ollama local (`racing_llama`, `racing_qwen`, `func_gemma`, `lfm_racing`, `ds_racing`) via Intel GPU, cloud fallbacks Groq (`openai/gpt-oss-20b`, `llama-3.3-70b`) + Gemini (`gemini-2.0-flash`), `sentence-transformers` + ChromaDB (local/persistent or Chroma Cloud)
- Memory: ChromaDB `form_insights` + JSONL + Honcho + `curated_memory` (agent_notes.md / user_prefs.md)
- Data: Betway API (`betway_api.py`), Racing Odds API, AtTheRaces (`attheraces_api.py`), RSS (BBC/Guardian/Mirror)
- Tests: `pytest` (44 tests), Black/flake8

**Edge — `cloudflare_mcp_edge/` (always-free Worker):**
- TypeScript, `@modelcontextprotocol/sdk` v1.29.0 (stateless `WebStandardStreamableHTTPServerTransport`), Zod, Wrangler
- D1 (244 form insights) + KV (live odds cache TTL 300s), OKF knowledge bundle (12 curated SA docs compiled via `node scripts/build-knowledge.js`)

**Frontend — `strike-tips-hud/` (Vercel):**
- Vite 8 + React 19 + TypeScript + Three.js, Tailwind CSS 4.0, Framer Motion, WebLLM (MLC-AI) for browser-local LLM, `middleware.ts` routing (Cloudflare vs Modal)

## Architecture & Conventions

**3-Layer Flow:**
```
Vercel HUD --middleware.ts--> Cloudflare Edge (OKF/D1/KV, 16 MCP tools)
                          \-> Modal Backend (FastAPI, Telegram bot, AI swarm, Dream/D SI, odds processing)
```
- `Docker` 4-container stack: `strike-bot-new` (FastAPI :8000), `odds-monitor-new`, `redis`, `ollama`, `redisinsight`
- `core_agent/core/strike_brain.py` singleton, `core_agent/agent/intent_classifier.py` (~0ms regex), gateway `core_agent/agent/providers/task_router.py`
- `core_agent/skills/swarm_researcher.py`: background loop `run_swarm_loop(interval=600)` + `enrich_snapshot_with_insights` — region detection from Betway `en` prefix, field blurbs, gated web-grounded Groq (6/cycle)
- `core_agent/core/telemetry.py` ring buffer + Redis `agent:telemetry` fanout, SSE `event:telemetry`
- `core_agent/core/heartbeat.py` (Dream Engine, 5-min)
- Paths centralized in `core_agent/config/paths.py` (`DATA_DIR=/app/data`); `PYTHONPATH=/app` in Docker
- Types: dataclasses + Enums + typed `Runner`/`RaceEvent`/`BetRecord`; pnpm/vite absolute imports; gambling-free tool names (`record_selection` not `place_bet`)

## Domain Knowledge

- **Markets:** Focus SA tracks (Fairview, Kenilworth, Greyville, etc.) plus global fallback; `en` field like `"USA: Saratoga"` drives region detection (USA/Japan/SA/UK etc.)
- **Math:** `BankrollGovernor` — Half-Kelly, 5% cap, 20% daily halt, Dream Stress Index DSI <20%→1.0x / 20-50%→0.75x / >50%→0.50x; `winProbability` + `edge` injected from daily-scan `value_bets` into `Runner`
- **RAG:** `save_racing_insight()` → ChromaDB `type:"racing_insight"` (region/source/ts) + `swarm_insights.json` per-outcomeId cache + `news_linked_<date>.json` dedupe
- **15 MAF tools** (`maf_tool_registry.py`): `search_racing_data` (Brave→Tavily→DDGS, `maf_search:{query}` cached), ATR movers/predictor/results, dreams

## Constraints & Standards

- Never bypass `BankrollGovernor` limits; `PAPER_TRADING=true` locally
- Keep tool names gambling-free for model filters
- Black (88 cols), 4-space Python, absolute imports, Google-style docstrings
- `navigator.storage.estimate()` + `persist()` before WebLLM weight download; `Cross-Origin-Opener-Policy: same-origin` / `Cross-Origin-Embedder-Policy: require-corp` for WASM threads
- Env: `.env` never committed; `STRIKE_TIPS_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `TELEGRAM_*`, `REDIS_URL`, `CHROMA_*`

## Key Paths

- `core_agent/skills/swarm_researcher.py`, `core_agent/core/telemetry.py`, `core_agent/core/adaptive_odds_monitor.py:enrich_snapshot_with_insights`
- `core_agent/routes/monitoring.py` (`GET /api/news`, `GET /api/telemetry`, `event:telemetry`), `core_agent/core/security.py` (`SAFE_PATHS`)
- `strike-tips-hud/src/engine/data-bridge.ts`, `strike-tips-hud/src/store/hud-store.ts` (`telemetry: []`), `strike-tips-hud/src/components/sidebar/TelemetryView.tsx`
- `strike-tips-hud/src/components/RaceCard.tsx` (sub-row banner, sortable headers, Edge col, per-row ⚡)

## Workflow

Use `/opsx:explore` (read-only) → `/opsx:propose` (this file's context + change artifacts) → `/opsx:apply` (tasks.md) → `openspec archive --yes`
