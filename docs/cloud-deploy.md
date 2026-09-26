# Cloud Deploy — Strike Tips Racing Bot (June 2026)

## Architecture (v3 — Standalone Ollama Cloud)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Modal Cloud (strike-tips-racing)              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  serve_api (FastAPI + MessageBus + AgentLoop)                 │   │
│  │                                                               │   │
│  │  ┌──────────┐   ┌───────────┐   ┌──────────────────┐        │   │
│  │  │ openai.py │──▶│ MessageBus│──▶│ AgentLoop         │        │   │
│  │  │ (API)     │   │ (queue)   │   │ → ContextBuilder   │        │   │
│  │  └──────────┘   └───────────┘   │ → TaskRouter       │        │   │
│  │                                 │ → AgentRunner      │        │   │
│  │  ┌──────────┐                   └──────────────────┘        │   │
│  │  │Telegram  │────▶ MessageBus                                │   │
│  │  │Webhook   │                                                │   │
│  │  └──────────┘                                                │   │
│  └─────────────────────────────────────────────────────────────┘   │
│         │                                  │                        │
│         ▼                                  ▼                        │
│  ┌─────────────────────┐     ┌──────────────────────────────────┐  │
│  │ Ollama Cloud Server  │     │ GroqProvider (INVALID API KEY)   │  │
│  │ (standalone)         │     │ GeminiProvider (429 rate-limited)│  │
│  │ gmpho--strike-tips-  │     │ → both fail → fallback to       │  │
│  │ ollama-cloud-ollama  │     │   Ollama cloud                  │  │
│  │ .modal.run           │     └──────────────────────────────────┘  │
│  │                      │                                          │
│  │ Models baked in:     │                                          │
│  │  • functiongemma:270m│                                          │
│  │  • qwen3.5:0.8b     │                                          │
│  │  • embeddinggemma:   │                                          │
│  │    300m              │                                          │
│  └─────────────────────┘                                          │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Data Volume (strike-tips-data) → /app/data                  │   │
│  │  • market_snapshot_latest.json (1.1MB)                       │   │
│  │  • atr_movers_snapshot.json (136KB)                          │   │
│  │  • atr_predictor_snapshot.json (11KB)                        │   │
│  │  • atr_results_snapshot.json (418KB)                         │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Vercel Frontend (strike-tips-hud.vercel.app)                        │
│  • Proxies /api/* and /v1/* → Modal                                 │
│  • Rewrites configured in vercel.json                                │
└──────────────────────────────────────────────────────────────────────┘
```

## Two Modal Apps

### App 1: `strike-tips-racing` (Main API)

| Entry Point | Type | Description |
|-------------|------|-------------|
| `serve_api` | `@modal.asgi_app()` | FastAPI + MessageBus + AgentLoop + TaskRouter |
| `register_webhook` | `@app.function()` | Register Telegram webhook URL |
| `daily_scan` | `@app.function(schedule=...)` | Scheduled scan at 05:00 SAST |
| `run_scan` | `@app.function()` | One-shot manual scan |
| `run_odds_monitor` | `@app.function()` | Continuous odds monitoring (12h) |

**Image**: Built from `Dockerfile` (no Ollama installed)
**Secrets**: `strike-tips-secrets`, `strike-tips-api-key`
**Volume**: `strike-tips-data` → `/app/data`
**Env**: `OLLAMA_HOST=https://gmpho--strike-tips-ollama-cloud-ollama.modal.run`

Deploy:
```bash
modal deploy -m core_agent.core.modal_app
```

### App 2: `strike-tips-ollama-cloud` (Standalone Ollama)

| Detail | Value |
|--------|-------|
| **File** | `core_agent/core/ollama_cloud.py` |
| **Image** | `debian_slim` (lightweight, no GPU) |
| **Models baked in** | `functiongemma:270m`, `qwen3.5:0.8b`, `embeddinggemma:300m` |
| **Endpoint** | `https://gmpho--strike-tips-ollama-cloud-ollama.modal.run` |
| **Container** | 2 CPU, 2048MB, `scaledown_window=300`, `min_containers=1` |
| **OLLAMA_KEEP_ALIVE** | 3600s (1hr keep-alive between requests) |
| **OLLAMA_MAX_LOADED_MODELS** | 2 (avoids OOM) |

Startup: non-blocking `subprocess.Popen(["ollama", "serve"])` → immediate return.
Cold start: ~51s (functiongemma:270m) to 19+ min (qwen3.5:0.8b).
Warm reuse: <10s for subsequent requests.

Deploy:
```bash
modal deploy -m core_agent.core.ollama_cloud
```

## MessageBus Architecture

```
                 ┌──────────────────┐
                 │  MessageBus       │
                 │  (asyncio.Queue)  │
                 │                   │
                 │  inbound Queue ───│── worker_loop(processor)
                 │  outbound Queue   │     │
                 │  _subscribers[]   │     ▼
                 └──────────────────┘  AgentLoop.process()
                         │                   │
                    subscribe()         AgentRunner.run_stream()
                         │                   │
                    OutboundMessage      TaskRouter.stream()
```

### Flow for /v1/chat/completions

1. `openai.py:handle_chat_completions()` creates `InboundMessage`, publishes to bus
2. `MessageBus.worker_loop` picks it up, calls `AgentLoop.process(msg)`
3. `AgentLoop` builds context via `ContextBuilder.build()` (injects snapshot, memory, history)
4. `AgentRunner.run_stream()` → `TaskRouter.stream()` processes:
   - **Phase 0**: `_try_snapshot_answer()` — read JSON snapshot data, format directly, no model call
   - **Phase 0b**: `_detect_specialist()` — map query keywords to specialist Ollama models
   - **Phase 1**: `_try_cloud_concurrent()` — Groq + Gemini with 5s deadline (both fail)
   - **Phase 2**: functiongemma:270m fallback (tool-capable cloud model)
   - **Phase 3**: Fast offline response for non-tool queries
   - **Phase 4**: Final fallback models (func_gemma, qwen3.5)
5. Response chunks flow back through MessageBus → subscriber → SSE response

### Key Providers

| Provider | Status | Key Issue |
|----------|--------|-----------|
| **Groq** | 403 Invalid API Key | Always fails immediately |
| **Gemini** | 429 Rate Limited | Always fails immediately |
| **Ollama cloud** (Modal) | Working | All requests fall through here |
| **Ollama local** (Docker) | Not used on Modal | 5 specialist models: racing_qwen, lfm_racing, func_gemma, racing_llama, ds_racing |

## Phase 0: Snapshot Data Access

`TaskRouter._try_snapshot_answer()` reads local JSON snapshot files and formats responses directly — no model call needed. This bypasses all cloud provider failures for common data-retrieval queries.

| Query Pattern | Snapshot File | Format |
|---------------|---------------|--------|
| "market movers" | `atr_movers_snapshot.json` | Horse, course, time, current odds, first show, movement % |
| "predictor tips" | `atr_predictor_snapshot.json` | Horse, prediction, data quality %, percent ahead |
| "recent results" | `atr_results_snapshot.json` | Course, date, time, runners with position and odds |
| "race at [track]" | `market_snapshot_latest.json` | Race name, time, runner count, weights, odds |

**Critical fix**: `_extract_user_query()` strips the context wrapper (snapshot/history/memory injected by `ContextBuilder`) and returns only the original user message. Without this, ALL queries matched the "race" keyword in the injected context.

## Provider Routing

```
User Query
    │
    ▼
_extract_user_query() → removes ContextBuilder wrapper
    │
    ▼
_try_snapshot_answer()
    │  ┌─ "market mover" → ATR_MOVERS_PATH
    │  ├─ "predictor|predict" → ATR_PREDICTOR_PATH
    │  ├─ "result" → ATR_RESULTS_PATH
    │  └─ "odds|race" → MARKET_SNAPSHOT_PATH → get_odds_snapshot()
    │
    ├─ snapshot found → return formatted text (NO model call)
    │
    ▼
_detect_specialist() → keyword → specialist model
    │
    ├─ specialist found → Ollama model override
    │
    ▼
_try_cloud_concurrent() → Groq + Gemini (5s deadline)
    │
    ├─ response → return
    │
    ▼
functiongemma:270m (Ollama cloud tool-capable model)
    │
    ├─ response → return
    │
    ▼
_needs_tools?
    │
    ├─ No → "offline mode" fast response
    │
    ▼
qwen3.5:0.8b (final fallback)
```

## Cloud Provider Status

| Provider | Key Status | Consequence |
|----------|-----------|-------------|
| **Groq** | `GROQ_API_KEY` invalid (403) | All Groq requests fail immediately → removed from concurrent providers or get valid key |
| **Gemini** | `GEMINI_API_KEY` rate-limited (429) | All Gemini requests fail → same action needed |

Both providers always fail, so all requests fall through to Ollama cloud. The 5s concurrent timeout is only hit on failures; a valid Groq key would return responses in ~1-3s.

## Vercel Frontend

- **URL**: `https://strike-tips-hud.vercel.app`
- **Rewrites** in `vercel.json`:
  ```json
  {
    "rewrites": [
      { "source": "/api/:path*", "destination": "https://gmpho--strike-tips-racing-serve-api.modal.run/api/:path*" },
      { "source": "/v1/:path*", "destination": "https://gmpho--strike-tips-racing-serve-api.modal.run/v1/:path*" }
    ]
  }
  ```
- **Streaming fix**: Changed `stream: false` → `stream: true` in `AIChat.tsx`

## Telegram Webhook

- **URL**: `https://gmpho--strike-tips-racing-serve-api.modal.run/telegram-webhook`
- **Mode**: webhook (not polling) — avoids update conflicts
- **Access control**: PIN-based auth (`/auth <PIN>`), checks `is_authorized()`
- **Flow**: Webhook receives message → creates InboundMessage → publishes to MessageBus → AgentLoop processes → OutboundMessage response → bot sends reply
- **Timeout**: 180s for long queries (scan, analysis)

## Quick Reference

```bash
# Deploy main API
modal deploy -m core_agent.core.modal_app

# Deploy standalone Ollama cloud
modal deploy -m core_agent.core.ollama_cloud

# Stop all containers (forces fresh deploy)
modal app stop strike-tips-racing -y

# Run one-off scan
modal run core_agent.core.modal_app::run_scan

# Register Telegram webhook
modal run core_agent.core.modal_app::register_webhook

# Sync data to volume
python3 sync_data_to_modal.py

# Local testing
python3 -m core_agent.core.strike_tips chat
```

## Limitations & Notes

- **Cold start**: Ollama cloud takes 51s–19min for first request per model. `min_containers=1` keeps one container warm. `OLLAMA_KEEP_ALIVE=3600` reuses loaded models for 1hr.
- **2 CPU limit**: Modal free tier only 2 CPUs; large models like `qwen3.5:0.8b` are memory-bound, not CPU-bound.
- **No GPU**: All models run on CPU. Next step: GPU tier for faster inference.
- **scaledown_window=300**: After deploy, old containers serve for 5min. Use `modal app stop` to kill immediately.
- **Data volume**: `strike-tips-data` persists snapshots across deploys. Run `sync_data_to_modal.py` to push local data.
- **Streaming timeout**: 25s `asyncio.wait_for` on bus subscriber prevents hanging past Vercel's 30s limit.
