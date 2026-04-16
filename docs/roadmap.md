# 🏇 Strike Tips Racing Bot - Development Roadmap

## Phase 1: Foundation & Stability (COMPLETED)
- [x] L7 Unified AI Intelligence Engine (Dispatcher/Analyst/Presenter chain).
- [x] Model Registry (Centralized config for 10 models).
- [x] ChromaDB Memory (Vector storage for race intelligence).
- [x] PDF Harvester (Computaform grounding).
- [x] Loop Protection (Async semaphore/state tracking for scans).

## Phase 2: Model Pipeline Architecture (COMPLETED)
- [x] **ModelPipeline class** - Delegation chain for query routing
- [x] **SpecialistExecutors** - Fast tool execution per model specialty
- [x] **IntentClassifier** - Keyword-based intent detection
- [x] **Model dropdown** with descriptions in frontend
- [x] **Tool descriptions** with use cases in maf_tool_registry.py
- [x] Updated Ollama Modelfiles with gambling-free prompts

### Model Specialties

| Model | Specialty | Speed | Tools |
|-------|-----------|-------|-------|
| `racing_llama` | Router + Synthesizer | Fast | All |
| `racing_qwen` | Fast Reads | ~1-2s | get_account_summary, search_racing_data |
| `func_gemma` | Write Operations | ~1-2s | record_selection, update_race_result |
| `lfm_racing` | Deep Analysis | ~2-3s | evaluate_race, run_daily_analysis |

## Phase 3: Auto-Result Updates (COMPLETED)
- [x] **ResultTracker** (`skills/result_tracker.py`)
  - DuckDuckGo search for race results
  - Parallel URL scanning via StealthEngine
  - Fuzzy matching for horse names
  - Auto-settle open bets
  - Telegram notifications

## Phase 4: Learning System (COMPLETED)
- [x] **LearningEngine** (`skills/learning/engine.py`)
  - Track ROI by track, distance, odds range
  - Track trainer and jockey performance
  - Track edge threshold performance
  - Historical data persistence

- [x] **AdaptiveAnalyzer** (`skills/learning/analyzer.py`)
  - Adjust probability estimates based on learning
  - Get recommendation for specific races
  - Identify best tracks/odds ranges

## Phase 5: Scheduler Updates (COMPLETED)
- [x] Result check every 5 minutes (12:00-20:00)
- [x] Learning update at 21:00
- [x] Daily scan at 11:00
- [x] End of day report at 20:00

## Current Status (Phase 6)

### High Priority - In Progress

#### 1. Dashboard Skill (Agent View) 📊
Real-time monitoring dashboard for agents.

**Features:**
- Real-time feed showing agent activity
- Active skills status (pending, completed, failed)
- Live bankroll and performance metrics
- Learning adjustments visualization

**Implementation:**
```
Frontend Tab: "Agent Dashboard"
├── Activity Feed (real-time)
├── Skill Status Grid
├── Performance Metrics
└── Learning Insights
```

#### 2. Enhanced Result Matching
Improve result accuracy.

**Features:**
- OCR for official results pages
- TAB4Racing direct scraping
- Race time tracking for accuracy

---

## Future Roadmap

### Medium Priority

#### 3. Voice Commands
Voice interface for Telegram.

**Features:**
- Speech-to-text via Telegram
- Voice responses for simple queries
- Command shortcuts

#### 4. Portfolio Optimization
Advanced bankroll management.

**Features:**
- Kelly Criterion implementation
- Dynamic stake sizing based on confidence
- Portfolio diversification

### Low Priority (Future Ideas)

#### 5. ML Prediction Model
Train custom prediction model.

**Features:**
- Feature engineering from historical data
- XGBoost/LightGBM model
- A/B testing against current system

#### 6. Multi-Track Support
Expand beyond SA racing.

**Features:**
- Support for UK, Australia, USA tracks
- Currency conversion
- Timezone handling

#### 7. API for Third-Party Integration
Public API for other services.

**Features:**
- REST API for selections
- Webhook notifications
- OAuth authentication

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INTERFACE                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  Frontend   │  │  Telegram   │  │   Agent     │       │
│  │   (Next.js) │  │    Bot      │  │  Dashboard  │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      API LAYER                              │
│              FastAPI on port 8000                          │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   ORCHESTRATION LAYER                        │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                ModelPipeline                          │  │
│  │  racing_llama (Router) → Specialist → Synthesizer   │  │
│  └─────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│   SPECIALISTS │    │   SPECIALISTS │    │   SPECIALISTS │
│   racing_qwen │    │   func_gemma  │    │   lfm_racing  │
│   Fast Reads  │    │ Write Ops     │    │ Deep Analysis │
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      SKILLS LAYER                            │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │   Result    │  │  Learning   │  │  Bankroll   │       │
│  │  Tracker    │  │   Engine    │  │  Governor   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐       │
│  │  ChromaDB   │  │   Analyzer  │  │  Telegram   │       │
│  │   Memory    │  │             │  │  Notifier   │       │
│  └─────────────┘  └─────────────┘  └─────────────┘       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   DATA / EXTERNAL                             │
│  ChromaDB Cloud | TAB4Racing | DuckDuckGo | Ollama        │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Stats

| Metric | Value |
|--------|-------|
| Total Tools | 11 |
| Local Models | 5 |
| Cloud Models | 4 |
| Learning Metrics | 8 (track, distance, odds, edge, trainer, jockey, etc.) |

---

## BACKLOG: FunctionGemma Integration
- **Status**: INTEGRATED (with gambling-free prompts)
- **Solution**: Updated Modelfiles with gambling-free language
- **Models Updated**: func_gemma, racing_qwen, lfm_racing

---

*Last Updated: 2026-03-25*
