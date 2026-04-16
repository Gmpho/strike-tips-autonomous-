# AGENTS.md - Agent Coding Guidelines

This document provides guidelines for AI agents working in this repository.

---

## Project Overview

**South African Horse Racing Intelligence System**
- **Python Backend** (`strike-tips/`): Core betting logic, scrapers, analysis engine
- **Next.js Frontend** (`strike-tips-frontend/`): React UI for the betting system

---

## Build / Lint / Test Commands

### Python Backend

```bash
# Install dependencies
cd strike-tips && pip install -r requirements.txt

# Run all tests
pytest

# Run single test file
pytest tests/test_analyzer.py

# Run specific test function
pytest tests/test_analyzer.py::TestRaceAnalyzer::test_edge_calculation -v

# Run with coverage
pytest --cov=strike_tips --cov-report=term-missing

# Format code (Black) & Lint
black . && flake8 .
```

### Next.js Frontend

```bash
# Install dependencies
cd strike-tips-frontend && npm install

# Development server
npm run dev

# Production build
npm run build

# Lint code
npm run lint
```

---

## Code Style Guidelines

### Python Backend

#### Imports
Standard library first, then third-party, then local. Use absolute imports.
```python
import os
import json
from dataclasses import dataclass
from typing import List, Optional, Dict

import httpx
import pydantic

from config.settings import BANKROLL
from skills.race_analysis.analyzer import RaceAnalyzer
```

#### Formatting
- **Black** for formatting (line length: 88)
- 4 spaces for indentation

#### Types
- Use **dataclasses** for data models
- Use **Enums** for fixed sets
- Use **pydantic** for API validation
- Always type hint functions
```python
class BetConfidence(Enum):
    STRONG_VALUE = "STRONG_VALUE"
    VALUE = "VALUE"
    MARGINAL = "MARGINAL"

@dataclass
class Runner:
    horse_name: str
    odds_decimal: float
    jockey: Optional[str] = None
```

#### Naming
- Classes: `PascalCase` (e.g., `RaceAnalyzer`)
- Functions: `snake_case` (e.g., `calculate_edge()`)
- Constants: `UPPER_SNAKE_CASE`
- Files: `snake_case.py`

#### Error Handling
- Use custom exceptions for domain errors
- Catch specific exceptions, avoid bare `except:`
- Log errors before re-raising

#### Docstrings
- Google-style docstrings with Args, Returns sections

---

### Next.js Frontend

- TypeScript for all files (`.ts` / `.tsx`)
- Functional components with hooks
- Tailwind CSS for styling
- Use Next.js App Router
- Avoid `any` type
- Run `npm run lint` before committing

---

## Project Structure

```
strike-tips/                          # Python backend
├── config/
│   ├── settings.py                 # Configuration
│   └── model_registry.py           # Model definitions
├── skills/
│   ├── race_analysis/              # Value bet engine
│   ├── bankroll_manager/           # Bankroll governance
│   ├── parsers/                   # Web scrapers
│   ├── memory/                     # ChromaDB vector memory
│   ├── learning/                   # Learning engine
│   └── notifications/              # Telegram bot
├── ai_pydantic.py                 # ModelPipeline (AI agents)
├── maf_tool_registry.py            # 11 MAF tools
├── result_tracker.py               # Auto-result updates
├── scheduler.py                    # Automation
├── telegram_agent_loop.py          # Telegram bot
├── routes/agent.py                 # API endpoints
├── ollama_configs/                # Ollama model configs
└── requirements.txt

strike-tips-frontend/                 # Next.js frontend
├── src/app/                        # App router pages
├── src/lib/api.ts                  # API utilities
└── package.json
```

---

## Key Conventions

1. **Environment Variables**: Use `.env` files, never commit secrets
2. **Bankroll Rules**: Never bypass max bet percentage (5%) or loss limits
3. **API Responses**: Always handle errors gracefully
4. **Testing**: Write tests for new features
5. **Type Safety**: Avoid `any` in TypeScript; use type annotations in Python

---

## Model Pipeline Architecture

The system uses a delegation chain for fast AI responses:

### Model Specialties

| Model | Specialty | Speed | Tools |
|-------|-----------|-------|-------|
| `racing_llama` | Router + Synthesizer | Fast | All |
| `racing_qwen` | Fast Reads | ~1-2s | get_account_summary, search_racing_data |
| `func_gemma` | Write Operations | ~1-2s | record_selection, update_race_result |
| `lfm_racing` | Deep Analysis | ~2-3s | evaluate_race, run_daily_analysis |

### 11 MAF Tools (Gambling-Free Names)

All tools use gambling-free naming to avoid model content filters:

| Tool | Purpose |
|------|---------|
| `evaluate_race` | Analyze race for value opportunities |
| `calculate_probability_edge` | Calculate edge percentage |
| `get_account_summary` | Check balance and profit/loss |
| `record_selection` | Record a racing selection |
| `update_race_result` | Update selection result |
| `calculate_max_position` | Calculate max safe stake |
| `search_past_races` | Search historical data |
| `search_racing_data` | Web search for racing info |
| `verify_race_exists` | Check if race is scheduled |
| `run_daily_analysis` | Scan all tracks for races |
| `get_odds_snapshot` | Get current odds |

### Intent Routing

```
User Query → IntentClassifier → SpecialistExecutors → Response
                         ↓
              banking_llama (Router) - Always involved
                         ↓
              Specialist based on intent:
              - BANKROLL → racing_qwen
              - SEARCH → racing_qwen
              - RECORD → func_gemma
              - ANALYZE → lfm_racing
              - SCAN → lfm_racing
```

---

## Learning System

The system tracks historical performance to improve predictions:

- **LearningEngine** (`skills/learning/engine.py`) - ROI tracking
- **AdaptiveAnalyzer** (`skills/learning/analyzer.py`) - Probability adjustment

### Tracked Metrics

- Track performance
- Distance performance
- Odds range performance
- Trainer/Jockey success rate
- Edge threshold performance

---

## Auto-Result Updates

**ResultTracker** (`skills/result_tracker.py`) automatically:

1. Searches for race results via DuckDuckGo
2. Scans result URLs via StealthEngine
3. Matches winners to open bets (fuzzy matching)
4. Auto-settles bets (WON/LOST)
5. Sends Telegram notifications
