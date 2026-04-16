# 🏇 Kimi Agent Strike Tips Racing Bot - Project Context

This repository contains the **Strike Tips** system, an AI-powered betting intelligence platform specifically designed for South African horse racing. It identifies value bets using probability edge analysis and enforces strict bankroll management.

## 🏛️ Architecture & Project Type

This is a **Full-Stack Code Project** consisting of:

-   **Backend (`strike-tips/`)**: 
    -   **Language**: Python 3.9+
    -   **Framework**: FastAPI (Web API), Core CLI orchestration.
    -   **Skills Layer**: Modular components for race analysis, bankroll management, web scraping (TAB4Racing), and Telegram notifications.
    -   **Storage**: JSON files in the `data/` directory for bankroll state, bet history, and scan results.
-   **Frontend (`strike-tips-frontend/`)**:
    -   **Framework**: Next.js 16+ (App Router), TypeScript.
    -   **Styling**: Tailwind CSS 4.0+, Framer Motion for animations, Lucide React for icons.
    -   **State Management**: React Hooks (useState, useEffect) with direct API integration via `fetch`.

## 🚀 Building and Running

### Prerequisites
-   Python 3.9+ installed.
-   Node.js 20+ installed.
-   A `.env` file in `strike-tips/` (see `.env.example`).

### 1. Backend Setup (Preferred: Docker)
The backend is containerized for stability and uses a "Turbo Build" strategy for speed.

```bash
# Navigate to backend
cd strike-tips

# Start the bot in the background
docker-compose up -d

# View real-time intelligence logs
docker logs -f strike-tips
```
*The API is available at `http://localhost:8000` with Swagger docs at `/docs`.*

### 2. Backend Setup (Manual / Fallback)
```bash
# Navigate to backend
cd strike-tips

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

### 3. Frontend Setup
```bash
# Navigate to frontend
cd strike-tips-frontend

# Install dependencies
npm install

# Start development server
npm run dev
```
*The UI will be available at `http://localhost:3000`.*

### 4. CLI Orchestrator (Inside Container)
```bash
# Run a manual scan using the running container
docker exec -it strike-tips python strike_tips.py scan
```

## 🧪 Testing

### Backend (Docker)
```bash
docker exec -it strike-tips pytest
```

### Backend (Local)
```bash
cd strike-tips
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
-   `strike-tips/strike_tips.py`: Main backend entry point.
-   `strike-tips/api.py`: FastAPI server definition.
-   `strike-tips/config/settings.py`: Global configuration and thresholds.
-   `strike-tips-frontend/src/app/page.tsx`: Main dashboard UI.
-   `strike-tips-frontend/src/lib/api.ts`: Frontend-to-backend communication layer.
-   `AGENTS.md`: Detailed coding guidelines for agents.

---

## 🔧 Recent Updates (March 25, 2026)

### Model Pipeline Architecture
- `ai_pydantic.py`: ModelPipeline class with IntentClassifier and SpecialistExecutors
- Fast tool execution (~1-2s) via Python code, no LLM overhead
- Telegram bot uses `brain.pipeline.chat()`

### Gambling-Free Tool Names (func_gemma compatible)
All 11 MAF tools renamed:
- `analyze_race` → `evaluate_race`
- `place_bet` → `record_selection`
- `settle_bet` → `update_race_result`
- `get_bankroll_status` → `get_account_summary`
- `calculate_max_stake` → `calculate_max_position`
- `query_memory` → `search_past_races`
- `search_racing_info` → `search_racing_data`
- `verify_race_event` → `verify_race_exists`
- `run_daily_scan` → `run_daily_analysis`
- `get_market_snapshot` → `get_odds_snapshot`

### Auto-Result Updates
- `skills/result_tracker.py`: ResultTracker with DuckDuckGo search + StealthEngine
- Fuzzy matching for horse names, auto-settle open bets
- Updated `scheduler.py` with result check job (every 5 min)

### Learning System
- `skills/learning/engine.py`: LearningEngine tracks ROI by track, distance, odds range
- `skills/learning/analyzer.py`: AdaptiveAnalyzer adjusts probability estimates
- Adjusts probabilities by ±30% max (MIN_SAMPLES=5 before applying)

### Dynamic Track Discovery (Real-Time) - ALL REGIONS
- `skills/race_schedule.py`: RaceScheduleService dynamically fetches today's tracks via TAB4Racing API
- **ALL 7 SA tracks always included** + international tracks grouped by region
- Regions: UK, Australia, USA, Ireland, France, Hong Kong, Japan
- `skills/parsers/pdf_harvester.py`: Supports SA/UK/International PDFs
- Same bankroll for all bets, results via DuckDuckGo
