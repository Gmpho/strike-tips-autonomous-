# 🐳 Docker Setup Guide - Strike Tips v2.0

> **📅 Last Updated:** April 2026 | **Version:** 2.0

This guide covers the 3-container Docker setup for Strike Tips.

---

## 🎯 Quick Reference

| Action | Command |
|:--- | :--- |
| 🚀 **Start All** | `docker compose up -d` |
| ⏹️ **Stop All** | `docker compose down` |
| 📺 **View Logs** | `docker logs -f strike-bot` |
| 🔄 **Restart** | `docker compose restart strike-bot` |
| 🏗️ **Rebuild** | `docker compose up -d --build` |

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     🚢 STRIKE TIPS DOCKER COMPOSE                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌────────────────────┐      ┌────────────────────┐      ┌────────────┐  │
│   │    📡 strike-bot │      │   🧠 ollama        │      │ 📊 odds-   │  │
│   │                   │      │                    │      │   monitor  │  │
│   │  FastAPI Server   │─────▶│  Local AI Models   │      │            │  │
│   │  Port: 8000       │      │  Port: 11434       │      │ Playwright │  │
│   │  /docs (Swagger) │      │  racing_llama      │      │ Scraper    │  │
│   │                   │      │  racing_qwen      │      │            │  │
│   │  PYTHONPATH=/app │      │  func_gemma        │      │ CPU: 0.8   │  │
│   │                   │      │  lfm_racing       │      │ RAM: 1.5G  │  │
│   └─────────┬──────────┘      └─────────┬──────────┘      └────┬─────┘  │
│             │                           │                      │        │
│             │         ┌─────────────────┴──────────────────┐      │        │
│             ▼         ▼                                   ▼      ▼        │
│       ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐           │
│       │  Data  │  │ Shared │  │ WSL2   │  │Network │  │ GPU    │           │
│       │Volume  │  │ Volume │  │  Lib  │  │ Bridge │  │Access  │           │
│       └────────┘  └────────┘  └────────┘  └────────┘  └────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📦 Container Details

### 1. 🐙 strike-bot (Main API)

```yaml
container_name: strike-bot
image: strike-tips-base:latest
ports:
  - "8000:8000"
environment:
  - PYTHONPATH=/app
  - DATA_DIR=/app/data
  - OLLAMA_HOST=http://ollama:11434
```

**Resources:**
- CPU: 1.0 core
- Memory: 2.0 GB

**Key Endpoints:**
- 📖 Swagger: `http://localhost:8000/docs`
- 💬 API: `http://localhost:8000/api/agent/chat`
- 📊 Health: `http://localhost:8000/api/agent/health`

---

### 2. 🧠 ollama (Local AI Models)

```yaml
container_name: ollama
image: uberchuckie/ollama-intel-gpu:latest
ports:
  - "11434:11434"
devices:
  - /dev/dxg:/dev/dxg
```

**Resources:**
- CPU: 1.5 cores
- Memory: 2.5 GB

**Available Models:**
```
racing_llama    # Router + synthesis (~1.3GB)
racing_qwen    # Fast reads (~1GB)
func_gemma      # Write operations (~300MB)
lfm_racing      # Deep analysis (~731MB)
ds_racing       # Reasoning (~1.1GB)
```

---

### 3. 📊 odds-monitor (Live Scraper)

```yaml
container_name: odds-monitor
command: python3 core_agent/core/adaptive_odds_monitor.py
deploy:
  resources:
    limits:
      cpus: '0.8'
      memory: '1.5G'
```

**Purpose:** Playwright-based scraper for live odds monitoring

---

## 🚀 Getting Started

### Step 1: Prerequisites

```bash
# Install Docker & Docker Compose
# On Windows: Enable WSL2
wsl --install

# Verify Docker
docker --version
docker compose version
```

### Step 2: Start Services

```bash
# From project root
cd /home/giftmpho/Kimi_Agent_Strike\ Tips\ Racing\ Bot

# Start all containers
docker compose up -d

# Check status
docker ps
```

### Step 3: Verify

```bash
# Test API
curl http://localhost:8000

# Test Ollama
curl http://localhost:11434/api/tags

# View all logs
docker compose logs -f
```

---

## 🔧 Configuration

### Environment Variables (.env)

```env
# 🚨 Required
TELEGRAM_BOT_TOKEN=xxx
TELEGRAM_CHAT_ID=xxx

# 🤖 AI Models
GROQ_API_KEY=xxx
GEMINI_API_KEY=xxx
OLLAMA_HOST=http://ollama:11434

# 🎛️ Model Assignments (optional)
MODEL_ORCHESTRATOR=local:llama3.2:1b
MODEL_REASONER=ds_racing
MODEL_SCRAPER=racing_qwen
MODEL_FUNC_CALL=func_gemma
MODEL_THINKING=lfm_racing

# 📊 Resources
OLLAMA_KEEP_ALIVE=-1
OLLAMA_FLASH_ATTENTION=1
```

---

## 🛠️ Troubleshooting

### ❌ Container Won't Start

```bash
# Check logs
docker logs strike-bot

# Check ports
netstat -tuln | grep -E '8000|11434'

# Restart Docker
systemctl restart docker
```

### ❌ Ollama Not Responding

```bash
# Check Ollama logs
docker logs ollama

# Test directly
curl http://localhost:11434/api/tags

# Restart Ollama
docker restart ollama

# Pull models manually
docker exec -it ollama ollama pull racing_llama
```

### ❌ Port Already in Use

```bash
# Find what's using the port
lsof -i :8000
lsof -i :11434

# Kill the process
kill -9 <PID>
```

### ❌ Out of Memory

```bash
# Check Docker stats
docker stats

# Reduce loaded models
# Edit .env: OLLAMA_MAX_LOADED_MODELS=1

# Restart
docker compose down && docker compose up -d
```

---

## 🔄 Updating & Rebuilding

### Update Code Only (Fast)

```bash
# Changes are hot-reloaded
docker compose up -d
```

### Full Rebuild

```bash
# Rebuild all images
docker compose up -d --build --no-cache
```

### Update Single Container

```bash
# Rebuild only strike-bot
docker compose up -d --build strike-bot
```

---

## 🌐 Windows-Linux Bridge (Legacy)

> **⚠️ This section is for reference only.** The new 3-container setup runs Ollama in Docker.

To connect Linux containers to Windows-hosted Ollama:

1. **Windows Side:**
   ```powershell
   setx OLLAMA_HOST "0.0.0.0"
   # Add firewall rule for port 11434
   ```

2. **Docker Side:**
   ```yaml
   extra_hosts:
     - "host.docker.internal:host-gateway"
   ```

3. **Environment:**
   ```
   OLLAMA_HOST=http://host.docker.internal:11434
   ```

---

## 📋 Common Commands Reference

```bash
# 🚀 Start
docker compose up -d

# ⏹️ Stop
docker compose down

# 📺 Logs
docker logs -f strike-bot        # All logs
docker logs --tail 100 strike-bot # Last 100 lines

# 🔄 Restart
docker compose restart

# 🧹 Clean up
docker compose down -v           # Remove volumes
docker system prune -a          # Clean unused images

# 📊 Stats
docker stats                    # Real-time resource usage

# 🐛 Debug
docker exec -it strike-bot /bin/bash
docker exec -it ollama /bin/bash
```

---

## ✅ Health Checks

```bash
# API Health
curl http://localhost:8000/api/agent/health | jq

# Ollama Health
curl http://localhost:11434/api/tags | jq

# Database (if applicable)
docker exec -it strike-bot python -c "
from core_agent.core.strike_brain import brain
print('Brain initialized:', brain._is_initialized)
"
```

---

## 🎓 Tips & Best Practices

1. **🚀 Use `docker compose up -d`** - Run in background
2. **📺 Check logs first** - Most issues visible in logs
3. **💾 Use volumes** - Persist data across rebuilds
4. **🔒 Limit resources** - Don't let one container hog RAM
5. **📦 Keep images small** - Use slim base images
6. **🧪 Test locally first** - Before deploying to production

---

*Happy Docker-ing! 🐳🚀*

---
*Status: Updated for v2.0 - April 2026*