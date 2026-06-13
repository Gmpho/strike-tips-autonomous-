# Core Pipeline
- Multi-source scraper with graceful fallbacks (Betway API → scraper → PDF harvester)
- AdaptiveOddsMonitor daemon collecting & merging Betway (45s) + Oddschecker (5min) into a single snapshot
- Snapshot cache layer (in-memory + Redis pub/sub + disk) for live odds distribution
- RaceAnalyzer with edge detection, Kelly staking, and value bet identification
- **ATR Data Resilience**: Tiered fetching (StealthyFetcher → Fetcher.get) with adaptive selectors and data integrity guards to prevent disappearing data cycle

# AI Agent System
- Model pipeline with TaskRouter routing through specialist agent models
- Multiple providers: Groq (now dead 403), Gemini (now dead 429), Ollama with fallback logic
- Intent classifier (regex) for routing user queries to the right tools
- MAF tool registry exposing 18 racing tools to AI agents
- Dream engine for background reasoning & heartbeat generation
- **Phase 0 Snapshot Answer**: Direct JSON snapshot reads bypass model calls entirely for 4 query types

# Infrastructure
- Redis-backed task queue, snapshot caching, and pub/sub
- Centralized HTTP client management with connection pooling
- **Standalone Ollama cloud on Modal**: 3 models baked in, separate from main API app
- MessageBus architecture with AgentLoop + ContextBuilder + TaskRouter
- API with auth middleware, monitoring, racing, betting, healing, admin routes
- Vercel frontend proxying `/api/*` and `/v1/*` to Modal backend
- Self-healing parsers that adapt to website changes

# Frontend / HUD
- strike-tips-hud/ dashboard with analytics visualizations, ROI tracking, healing view, workflow display
- Streaming AI chat via `AIChat.tsx` with `stream: true`

# Memory
- Dual memory: ChromaDB (race intelligence RAG) + Honcho (user/agent memory)
- Intelligence cache manager for historical odds baselines
- Learning engine that adjusts probabilities based on results

# Lessons Learned (Earlier June 2026)
- **Resilient Fetching**: StealthyFetcher (headless Chromium + Cloudflare solver) solves Cloudflare/Fastly challenges; Fetcher.get as fast fallback
- **Adaptive Selectors**: Scrapling's adaptive=True on Selector initialization provides self-healing against HTML changes (40% similarity threshold)
- **Data Integrity**: Guard clause `if atr_data:` prevents overwriting good snapshots with empty arrays during temporary API blanks
- **Persistent Browser Profile**: Maintaining session cookies at `/app/data/browser_profile` reduces challenge frequency across container restarts
- **Monitoring Importance**: Tracking fetch-tier effectiveness helps observe resolver performance (StealthyFetcher vs Fetcher.get)

# Lessons Learned (Jun 13, 2026 — Streaming, Ollama Cloud, Snapshot Routing)

## MessageBus Architecture
- **Two subscribers to the bus**: `openai.py` and `telegram.py` both publish InboundMessage and subscribe for OutboundMessage. The `MessageBus.worker_loop(processor)` consumes InboundMessage and calls `AgentLoop.process()`. Multiple subscribers receive the same broadcast — unsubscribe after timeout to avoid leaking queues.
- **25s timeout on bus subscriber**: Vercel's edge functions have a 30s limit. `asyncio.wait_for(sub.get(), timeout=25.0)` prevents hanging connections. The non-streaming path also uses the same timeout pattern.
- **ContextBuilder wrapping**: `AgentLoop` wraps the user's message inside a context string via `ContextBuilder.build()` which injects `[LIVE SNAPSHOT]`, `[USER MEMORY]`, `[FORM INSIGHTS]`, `[HISTORY]`, and `[QUERY]` sections. This means `messages[-1]["content"]` is NOT the original user query — it's a multi-section context document.

## Standalone Ollama Cloud
- **Dockerfile separation**: The main app Dockerfile no longer installs Ollama (was failing on 404 during build). Instead, a separate Modal app (`ollama_cloud.py`) runs a standalone Ollama server with 3 baked-in models.
- **Non-blocking serve startup**: Use `subprocess.Popen(["ollama", "serve"])` instead of `proc.wait()` — the latter blocks indefinitely. The web_server decorator needs immediate return to signal readiness.
- **3-model bake-in**: Only 3 small models (`functiongemma:270m`, `qwen3.5:0.8b`, `embeddinggemma:300m`) fit on free tier (2GB RAM, 2 CPU). 5 heavier specialist models stay local-only.
- **OLLAMA_KEEP_ALIVE=3600**: Keeps loaded models in memory for 1hr between requests. Combined with `OLLAMA_MAX_LOADED_MODELS=2`, prevents repeated cold-starts while avoiding OOM.
- **Cold start reality**: 51s (functiongemma) to 19+ min (qwen3.5) on first request to a new model. Subsequent requests within the keep-alive window are <10s.

## Snapshot Routing (Phase 0)
- **Direct JSON reads beat model calls**: For queries about market movers, predictor tips, results, and odds, reading local JSON files and formatting text is faster and more reliable than routing through any LLM (especially with dead cloud providers).
- **Word-boundary regex for plurals**: `\b{keyword}\b` fails on "results" when keyword is "result". Changed to `\b{keyword}[a-z]*` to match plural forms. Applied in both `_detect_specialist()` and `_needs_tools()`.
- **Context injection of keywords**: Because ContextBuilder wraps the user query inside a larger context that includes snapshot data (which contains "race", horse names, etc.), checking `messages[-1]["content"]` for keywords causes false matches. Solution: `_extract_user_query()` parses out the `[QUERY]` section.
- **asyncio.iscoroutinefunction exists in 3.10**: The function exists in Python 3.10+ (returning True for async functions). No need to fall back to `inspect.iscoroutinefunction`.

## Cloud Provider Death
- **Groq API key is 403 invalid**: `curl` confirmed `{"error":{"message":"Invalid API Key","code":"invalid_api_key"}}`. All Groq requests fail immediately.
- **Gemini is 429 rate-limited**: Also dead. Both cloud providers effectively don't work.
- **All traffic hits Ollama cloud fallback**: Tiny models (270M–0.8B) generate weak responses. Only Phase 0 snapshot answers produce reliable results. Either get valid keys or remove them from the concurrent provider list.

## Groq Provider Fixes
- **Tool parameter schemas from inspect**: `groq.py:_get_tools()` builds `parameters` from `inspect.signature()` instead of hardcoded schemas. `required` handles `None` defaults correctly.
- **Strike injection**: `_execute_tool` checks function signature and injects `strike=brain.strike` from `core_agent.core.strike_brain.brain` if the tool accepts it. Prevents "StrikeTips not initialized" errors.
- **max_tokens 400→800**: Gives the model more room for tool reasoning. Combined with 30s timeout (was 15s).

## Router / Specialist Fixes
- **Specialist route try/except**: The specialist model stream loop was unguarded. A model failure (OOM, timeout) would crash the route. Wrapped with `try/except Exception`.
- **Ollama JSON decode hardening**: `json.loads(line)` inside `/api/generate` response parsing was unguarded. Wrapped with `try/except json.JSONDecodeError`.
- **Tool keywords expanded**: "market", "mover", "predictor", "prediction", "probability", "stake", "bank", "race", "runner", "horse", "jockey", "trainer", "show", "list", "give", "what" added to improve detection of tool-related queries.

## Ollama Internal Calls
- **curl_cffi → httpx**: Replaced `curl_cffi` with `httpx.AsyncClient(timeout=600.0)` for Ollama HTTP calls. Simpler, no compilation issues, better timeout control.
- **Stateful `<think>` tag stripping**: Recursive `_strip_think()` tracks open/close tags across chunk boundaries. Prevents partial tags from appearing in responses.

## Docker / Infrastructure
- **Ollama removed from main Dockerfile**: Base image no longer installs Ollama (was failing on `install.sh` 404). Main app connects to the standalone Ollama cloud instead.
- **OLLAMA_HOST URLs updated**: 4 files pointed to old localhost URL. Updated to the new cloud URL.
- **modal app stop for fresh deploy**: After `modal deploy`, old containers can still serve for up to `scaledown_window=300` seconds. Use `modal app stop <app-name> -y` to kill them immediately.
- **Scraper asyncio.wait_for**: All 5 `asyncio.to_thread(self._fetch, ...)` calls wrapped with `asyncio.wait_for(..., timeout=60)` to prevent hanging on slow scrapes.
