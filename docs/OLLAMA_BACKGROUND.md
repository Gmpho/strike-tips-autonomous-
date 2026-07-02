# 🤖 Ollama Background Architecture

This document describes how **Ollama** is utilized exclusively for **background intelligence operations** within the Strike Tips platform. 

To maintain maximum UI responsiveness, prevent VRAM/GPU thread contention on the main web host, and optimize token throughput, Strike Tips strictly separates user-facing chat (handled by Cloud API or Browser WebGPU) from backend task execution (handled by Ollama).

---

## 🏛️ Separation of Concerns

```
┌────────────────────────────────────────────────────────────────────────┐
│                          STRIKE TIPS GATEWAY                           │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                  ┌─────────────────┴─────────────────┐
                  ▼                                   ▼
       [ USER-FACING CHAT ]                 [ BACKGROUND TASKS ]
  ⚡ WebGPU / Groq / Gemini Flash       🤖 Local Ollama Models (WSL2 GPU)
  • Dynamic code-splitting (43KB boot)  • Parallel scans & dreams
  • Paused WebGL rendering on chat      • Auto-Result updates & settlement
  • Zero server load on mobile          • Vector DB embeddings (ChromaDB)
```

1. **User-Facing Chat**: Handled locally in the browser via **WebGPU (WebLLM)** or routed to high-throughput cloud endpoints (**Groq Llama 70B** / **Gemini Flash**).
2. **Background Processes**: Run inside the Docker container stack using local **Ollama** running on WSL2 with dedicated GPU acceleration.

---

## 🤖 Dedicated Ollama Models & Roles

Strike Tips orchestrates **five specialist models** inside Ollama, each loaded with custom instructions via Docker Modelfiles:

| Model | Task / Specialty | Key Module / Skill | API Format |
|-------|------------------|--------------------|------------|
| **`ds_racing:latest`** | Deep Reasoning (DeepSeek R1 base) | `skills/race_analysis` (implied probability edge) | `generate` |
| **`lfm_racing:latest`** | Step-by-Step Analysis (LFM 2.5 base) | `skills/dreamer.py` (simulating race scenarios) | `generate` |
| **`racing_qwen:latest`** | Fast Reads & Quick Predictions | `core/strike_tips.py` (daily racecard lookup) | `generate` |
| **`func_gemma:latest`** | Structured Tool & Write Operations | `tools/maf_tool_registry.py` (recording/settling bets) | `generate` |
| **`racing_llama:latest`** | Search Summarization & Reranking | `skills/search_service.py` (Summarizing live web results) | `generate` |
| **`embeddinggemma:300m`** | Vector Embedding Generation | `skills/memory/chroma_memory.py` (Memory RAG R/W) | Embedding |

---

## ⚙️ Background Workflows

### 1. The Daily Scan (`strike_tips.py scan`)
Every morning at the scheduled time, the orchestrator triggers the following flow:
1. `racing_qwen` reads scraped racecards and filters out scratchings.
2. `ds_racing` evaluates the runner form guides and calculates custom estimated probabilities.
3. If an advantage edge exists ($P_{\text{estimated}} - P_{\text{implied}} > 5\%$), it triggers the bankroll sizing engine.
4. `func_gemma` executes the write operation to save the bet record in `data/bet_history.json`.

### 2. Scenario Simulation ("Dreaming")
When custom weather or track events are triggered (either via Telegram `/dream` or scheduler):
1. The **Dream Engine** (`skills/dreamer.py`) calculates going shifts, wind impact, and scratch adjustments.
2. The engine evaluates how specific going shifts, weather, or scratchings impact runner performance, generating heuristic probability shifts + a single randomized trial.
3. Results are saved as vector documents in **ChromaDB** using `embeddinggemma:300m`.
4. The **Bankroll Governor** query pulls these records to calculate the **Dream Stress Index (DSI)** based on the simulated scenario outcome to scale down Kelly betting sizes under volatile/adverse conditions.

### 3. Bayesian Performance Calibration (`skills/learning/`)
As actual race results are tracked:
1. The **Result Tracker** (`skills/result_tracker.py`) uses DuckDuckGo + StealthEngine to fuzzy-match winners.
2. The **Learning Engine** executes a Beta-Binomial update blending the simulated dreams (priors) with real results:
   $$\text{Prior Decay} = e^{-0.15 \times \text{real\_bets}}$$
3. This adjusts probability estimates for future scans without needing full model retrainings.

---

## 🛠️ Configuration & Settings

Local Ollama models are configured inside `core_agent/config/model_config.py` and driven by the backend `.env` variables:

```ini
# core_agent/.env
OLLAMA_HOST=http://localhost:11434
MODEL_REASONER=ds_racing:latest
MODEL_THINKING=lfm_racing:latest
MODEL_SCRAPER=racing_qwen:latest
MODEL_FUNC_CALL=func_gemma:latest
MODEL_EMBEDDER=embeddinggemma:300m
```

By removing these models from the user chat options, we guarantee that the Ollama host is never blocked or resource-throttled by interactive chat requests, preserving its entire compute capacity for heavy background race calculations.
