# 🏇 Kimi Agent Strike Tips Racing Bot - Project Context

This repository contains the **Strike Tips** system, an AI-powered betting intelligence platform specifically designed for South African horse racing. It identifies value bets using probability edge analysis and enforces strict bankroll management.

## 🏛️ Architecture & Project Type

This is a **Full-Stack Code Project** consisting of:

-   **Backend (`core_agent/`)**: 
    -   **Language**: Python 3.9+
    -   **Framework**: FastAPI (Web API), Core CLI orchestration.
    -   **AI Layer**: Direct httpx calls to Ollama (no Pydantic AI dependency)
    -   **Skills Layer**: Modular components for race analysis, bankroll management, web scraping (TAB4Racing), and Telegram notifications.
    -   **Storage**: JSON files in the `data/` directory for bankroll state, bet history, and scan results.
-   **Frontend (`strike-tips-hud/`)**:
    -   **Framework**: Vite 8+, React 19+, TypeScript.
    -   **Styling**: Tailwind CSS 4.0+, Framer Motion for animations, Lucide React for icons.
    -   **State Management**: React Hooks (useState, useEffect) with direct API integration via `fetch`.
-   **Docker Setup**: 3-container setup (strike-bot, ollama, odds-monitor)

## 🚀 Building and Running

### Prerequisites
-   Python 3.9+ installed.
-   Node.js 20+ installed.
-   A `.env` file in `strike-tips/` (see `.env.example`).

### 1. Backend Setup (Preferred: Docker)
The backend is containerized for stability and uses a "Turbo Build" strategy for speed.

```bash
# Navigate to project root
cd /home/giftmpho/Kimi_Agent_Strike\ Tips\ Racing\ Bot

# Start all containers (strike-bot, ollama, odds-monitor)
docker compose up -d

# View real-time intelligence logs
docker logs -f strike-bot
```
*The API is available at `http://localhost:8000` with Swagger docs at `/docs`.*

### 2. Backend Setup (Manual / Fallback)
```bash
# Navigate to core_agent
cd core_agent

# Create and activate virtual environment
python -m venv venv

# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the FastAPI server
python api.py
```

### Frontend Setup
```bash
# Navigate to frontend
cd strike-tips-hud

# Install dependencies
npm install

# Start development server
npm run dev
```
*The UI will be available at `http://localhost:5173`.*

### 4. CLI Orchestrator (Inside Container)
```bash
# Run a manual scan using the running container
docker exec -it strike-bot python core_agent/core/strike_tips.py scan
```

## 🧪 Testing

### Backend (Docker)
```bash
docker exec -it strike-bot pytest
```

### Backend (Local)
```bash
cd core_agent
pytest
```

### Frontend (Next.js)
```bash
cd strike-tips-frontend
npm run lint                # Run ESLint
```

## 🛠️ Development Conventions

### General
-   **Environment Variables**: Never commit `.env` files. Use `strike-tips/.env.example` as a template.
-   **Data Storage**: All persistent data (bets, bankroll) is stored in the `data/` directory.

### Python Backend
-   **Formatting**: Use **Black** for formatting (line length 88).
-   **Linting**: Use **Flake8**.
-   **Types**: Use **dataclasses** for models and **type hints** for all functions.
-   **Structure**: Logic is separated into "skills" (`skills/race_analysis`, `skills/bankroll_manager`, etc.).

### Next.js Frontend
-   **Types**: Use TypeScript for all components and API utilities. Avoid `any`.
-   **Components**: Functional components with hooks.
-   **Styling**: Use Tailwind CSS utility classes.
-   **API Client**: Centralized in `src/lib/api.ts`.

## 💰 Core Business Logic (The "Governor")
The system follows a strict "God Mode" betting strategy:
-   **Max Stake**: Never more than 5% of total bankroll per bet.
-   **Daily Loss Limit**: Stop scanning/betting if 20% of bankroll is lost in a day.
-   **Value Betting**: Only bets when `Estimated Probability - Implied Probability > 5%`.
-   **Kelly Criterion**: Uses Half-Kelly (0.5 fraction) for conservative staking.

## 📁 Key Files
-   `core_agent/core/strike_tips.py`: Main backend entry point.
-   `core_agent/api.py`: FastAPI server definition.
-   `core_agent/config/model_config.py`: Centralized model configuration.
-   `core_agent/agents/ai_pydantic.py`: ModelPipeline with IntentClassifier.
-   `core_agent/tools/maf_tool_registry.py`: 11 MAF tools.
-   `strike-tips-frontend/src/app/page.tsx`: Main dashboard UI.
-   `strike-tips-frontend/src/lib/api.ts`: Frontend-to-backend communication layer.
-   `docs/AGENTS.md`: Detailed coding guidelines for agents.

---

## 🔧 Recent Updates (April 2026)

### Refactored to core_agent/
- Moved all backend code from `strike-tips/` to `core_agent/`
- Updated paths: `skills/`, `config/`, `routes/`

### New AI Architecture
- Removed Pydantic AI dependency - now uses direct `httpx` calls to Ollama
- New `ModelPipeline` with regex-based `IntentClassifier` (~0ms routing)
- Fallback chain: local Ollama → Groq (cloud) → Gemini (cloud)

### Docker 3-Container Setup
- `strike-bot`: FastAPI backend on port 8000
- `ollama`: Intel GPU with WSL2 on port 11434
- `odds-monitor`: Playwright scraper for live odds

### Model Pipeline
- `racing_llama`: Router + fast reads (Local)
- `racing_qwen`: Fast reads (balance, odds) (Local)
- `func_gemma`: Write ops (record, update) (Local)
- `lfm_racing`: Deep analysis (evaluate, scan) (Local)
- `ds_racing`: Reasoning (probability edge) (Local)
- **Healing Swarm (Cloud Ollama)**: 7-model pool for autonomous repair (`nemotron`, `glm`, `qwen3.5`, `gemma4`, `kimi`, `gemini-flash`).
- **Parallel Tasks**: `kimi-k2-thinking:cloud` for multi-race simultaneous dispatch.

### Gambling-Free Tool Names (unchanged)
All 11 MAF tools use gambling-free naming:
- `evaluate_race`, `run_daily_analysis`, `get_account_summary`
- `record_selection`, `update_race_result`, `calculate_probability_edge`
- `calculate_max_position`, `search_racing_data`, `search_past_races`
- `verify_race_exists`, `get_odds_snapshot`

### Auto-Result Updates
- `skills/result_tracker.py`: ResultTracker with DuckDuckGo search + StealthEngine
- Fuzzy matching for horse names, auto-settle open bets

### Learning System
- `skills/learning/engine.py`: LearningEngine tracks ROI by track, distance, odds range
- `skills/learning/analyzer.py`: AdaptiveAnalyzer adjusts probability estimates
- Adjusts probabilities by ±30% max (MIN_SAMPLES=5 before applying)

### Dynamic Track Discovery (Real-Time) - ALL REGIONS
- `skills/race_schedule.py`: RaceScheduleService dynamically fetches today's tracks via TAB4Racing API
- **ALL 7 SA tracks always included** + international tracks grouped by region
- Regions: UK, Australia, USA, Ireland, France, Hong Kong, Japan

### Recent Updates (July 2026 - v2.2)
- **WebGPU Search Grounding**: Added `/api/agent/context` endpoint fetching real-time odds, vector insights, and live DuckDuckGo web search results to feed local browser-side models.
- **Bayesian Prior Decays**: Implemented statistical prior decay inside the Bayesian Learning Engine using alternative scenarios (dreams) as prior distributions that decay exponentially as real bets accumulate.
- **DSI Kelly Staking & Sizing Checks**: Integrated background dream simulations to calculate the **Dream Stress Index (DSI)** and automatically scale down Kelly betting sizes (1.0x, 0.75x, 0.50x) under volatile/adverse conditions.
- **ChromaDB Conflict Resilience**: Added fallback handling to automatically bypass and reuse persisted embedding functions during schema conflicts on boot.
