# Deploy — Strike Tips Racing Bot

## Architecture

```
┌──────────────────────────────────────────────────┐
│                  Modal Cloud                      │
│  ┌────────────────────────────────────────────┐  │
│  │         strike-tips-racing App              │  │
│  │                                              │  │
│  │  serve_api (FastAPI + Scheduler) ───────┐   │  │
│  │  run_scan (one-shot scan)               │   │  │
│  │  run_odds_monitor (continuous odds)      │   │  │
│  └──────────────────────────────────────────┘   │
│         │                                       │
│         ▼                                       │
│  ┌──────────────────┐    ┌───────────────────┐  │
│  │  strike-tips-data │    │  strike-tips-secrets│ │
│  │  Volume (persist) │    │  Secret (env vars) │  │
│  └──────────────────┘    └───────────────────┘  │
│         │                                       │
└─────────┼───────────────────────────────────────┘
          │
          ▼
┌──────────────────┐
│   Redis Cloud     │
│  af-south-1 free  │
│  30MB, v8.4       │
│  Stack + modules  │
└──────────────────┘
```

## Deployment Steps

### 1. Modal App

**File**: `core_agent/core/modal_app.py`

Five entry points deployed:

| Entry Point | Type | Description |
|-------------|------|-------------|
| `serve_api` | `@modal.asgi_app()` | FastAPI app + internal scheduler, always-on |
| `register_webhook` | `@app.function()` | One-shot: register Telegram webhook URL |
| `daily_scan` | `@app.function(schedule=...)` | Scheduled scan at 05:00 SAST daily |
| `run_scan` | `@app.function()` | One-shot manual scan |
| `run_odds_monitor` | `@app.function()` | Continuous odds monitoring (12h timeout) |

**Image**: Built from `Dockerfile` using `modal.Image.from_dockerfile("Dockerfile")`

**Resources**:
- Memory: 2048MB (serve_api, run_scan), 1536MB (odds_monitor)
- Timeout: 3600s (serve_api, run_scan), 43200s (odds_monitor)
- Volume: `strike-tips-data` mounted at `/app/data`
- Secrets: `strike-tips-secrets` (all env vars)

**Deploy command**:
```bash
modal deploy core_agent.core.modal_app
```

### 2. Modal Secrets (`strike-tips-secrets`)

Contains all environment variables needed by the app:

| Variable | Source |
|----------|--------|
| `TELEGRAM_BOT_TOKEN` | Telegram BotFather |
| `TELEGRAM_CHAT_ID` | Telegram chat |
| `GEMINI_API_KEY` | Google AI Studio |
| `CHROMA_HOST` / `CHROMA_PORT` | ChromaDB |
| `REDIS_URL` | Redis Cloud connection string |

Note: `modal secret create` refuses to overwrite existing secrets. Must delete first:
```bash
modal secret delete strike-tips-secrets
modal secret create strike-tips-secrets KEY1=val1 KEY2=val2 ...
```

### 3. Redis Cloud

| Detail | Value |
|--------|-------|
| Name | `database-MPMOLTFS` |
| Plan | Free 30MB (Essentials) |
| Region | AWS af-south-1 (Cape Town) |
| Redis | v8.4, standalone |
| Endpoint | (in Modal secrets as `REDIS_URL`) |
| Password | Random 32-char alphanumeric |
| Modules | search, RedisTimeSeries, RedisBloom, RedisJSON |

### 4. Data Sync

**File**: `sync_data_to_modal.py`

Syncs local ChromaDB and data to Modal volume:
```bash
python3 sync_data_to_modal.py
```

### 5. Code Support

`core_agent/core/task_queue.py:19` already supports `REDIS_URL` env var:
```python
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
```

No code changes needed — Modal app uses the cloud Redis URL from secrets, local docker-compose stays on `redis://redis:6379/0`.

### 6. Telegram Webhook

**Endpoint**: `POST /telegram-webhook` (injected into FastAPI app inside `serve_api`)

Registered via:
```bash
modal run core_agent.core.modal_app::register_webhook
```

This calls Telegram's `setWebhook` API to point at `https://gmpho--strike-tips-racing-serve-api.modal.run/telegram-webhook`. Bot replies use the `brain.pipeline.chat()` pipeline and send responses back in Markdown.

### 7. Daily Scan Cron

**Schedule**: `05:00 SAST` every day (`0 5 * * *`, timezone `Africa/Johannesburg`)

Runs the same `strike_tips.py scan` as the manual `run_scan`, but triggered automatically by Modal's scheduler. The internal `StrikeTipsScheduler` (running inside `serve_api`) also handles background jobs (check_odds, tip sweeps, purges, etc.).

### 8. MCP Configuration (`.mcp/redis.json`)

Two MCP servers configured side by side:

| Server | Tool | Purpose |
|--------|------|---------|
| `redis` | `redis-mcp-server` | Local Redis (Docker, port 6379) |
| `redis-cloud` | `mcp/redis-cloud` (Docker) | Redis Cloud API management |

Local Redis MCP tools for data queries. Cloud MCP tools for managing subscriptions/databases via API keys.

### 9. Limitations (Free Tier)

| Feature | Supported? |
|---------|-----------|
| Password auth | ✅ |
| TLS encryption | ❌ (paid plans only) |
| IP whitelist | ❌ (paid plans only) |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/agent/scan` | POST | Run daily scan |
| `/api/agent/health` | GET | Orchestrator health |
| `/api/system/health` | GET | System vitals |
| `/api/status` | GET | Bankroll status |
| `/api/tracks` | GET | Track schedule |
| `/api/scan/{track}` | GET | Scan specific track |
| `/telegram-webhook` | POST | Telegram bot webhook |

## Quick Reference

```bash
# Deploy
modal deploy core_agent.core.modal_app

# Run one-off scan
modal run core_agent.core.modal_app::run_scan

# Register Telegram webhook
modal run core_agent.core.modal_app::register_webhook

# Check deployed app logs
modal app logs <app-id>

# Sync data to volume
python3 sync_data_to_modal.py
```
