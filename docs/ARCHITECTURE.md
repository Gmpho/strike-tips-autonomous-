# Strike Tips - Architecture Documentation (v2.0 - April 2026)

## System Overview

Strike Tips is built on a modular skill-based architecture inspired by agent systems. Each skill is self-contained and can operate independently.

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#1E3A5F',
      'primaryTextColor': '#FFF',
      'primaryBorderColor': '#2563EB',
      'lineColor': '#94A3B8',
      'secondaryColor': '#0F172A',
      'tertiaryColor': '#1E293B'
    }
  }
}%%
graph TB
    subgraph TITLE["🏇 STRIKE TIPS SYSTEM v2.0 — core_agent/"]
        direction LR
    end
    style TITLE fill:#1E3A5F,stroke:#2563EB,stroke-width:3px,color:#FFD700,font-size:16px

    %% ─── FRONTEND ───
    subgraph FE["🎨 Frontend Layer"]
        HUD["Web HUD<br/>(Vite/Vanilla TS)<br/>Port: 5173"]
    end
    style FE fill:#1E3A5F,stroke:#3B82F6,stroke-width:2px,color:#DBEAFE

    %% ─── BACKEND ───
    subgraph BE["⚙️ Backend — FastAPI (Port 8000)"]
        SB["🧠 Strike Brain<br/>(Singleton)"]
        MP["🤖 ModelPipeline"]
        INTENT["⚡ IntentClassifier<br/>(Regex ~0ms)"]
        ORCH["🔀 UnifiedOrchestrator"]
        SB --- MP
        MP --- INTENT
        MP --- ORCH
    end
    style BE fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#D1FAE5

    %% ─── SKILL LAYER ───
    subgraph SKILLS["🧩 Domain Skills"]
        RA["🏇 Race Analysis<br/>• Value Engine<br/>• Kelly Staking<br/>• Form Analysis"]
        BGOV["💰 Bankroll Governor<br/>• Max 5% Rule<br/>• Daily Loss Limits<br/>• P&L Tracking"]
        NOTIF["📱 Notifications<br/>• Daily Tips<br/>• Bet Alerts<br/>• Results"]
    end
    style SKILLS fill:#4C1D95,stroke:#8B5CF6,stroke-width:2px,color:#EDE9FE
    ORCH --> RA & BGOV & NOTIF

    %% ─── FALLBACK CHAIN ───
    subgraph FALLBACK["⬇️ LLM Fallback Chain"]
        GROQ["Groq Cloud<br/>llama-3.3-70b"]
        GEMINI["Gemini Chain<br/>2.0-flash→2.5-flash→2.5-pro"]
        LOCAL["Ollama Local<br/>racing_llama, racing_qwen<br/>func_gemma, lfm_racing, ds_racing"]
    end
    style FALLBACK fill:#312E81,stroke:#6366F1,stroke-width:2px,color:#E0E7FF
    ORCH -.- GROQ --> GEMINI --> LOCAL

    %% ─── MEMORY ───
    subgraph MEMORY["💾 Memory Systems"]
        CHROMA["ChromaDB<br/>(Cloud / Local)"]
        HONCHO["Honcho<br/>(User Memory + Dreams)"]
        EMBED["Embedding: Ollama→Gemini→Default"]
    end
    style MEMORY fill:#164E63,stroke:#06B6D4,stroke-width:2px,color:#CFFAFE
    INTENT -.-> CHROMA & HONCHO
    CHROMA --- EMBED

    %% ─── DATA LAYER ───
    subgraph DATA["🗄️ Data Ingestion"]
        TAB["📄 TAB4Racing<br/>(Racecards)"]
        PARSER["🔧 Adaptive Parser<br/>(Self-Healing)"]
        ODMON["👁️ Live Odds Monitor<br/>(Playwright)"]
        PDF["📑 PDF Harvester<br/>(Form Guides)"]
    end
    style DATA fill:#1F2937,stroke:#6B7280,stroke-width:2px,color:#F3F4F6
    SB --> TAB & PARSER & ODMON & PDF

    %% ─── BACKGROUND ───
    subgraph BG["⏰ Background Processes"]
        HEART["💓 Heartbeat<br/>(Every 5 min)"]
        DREAM["💭 Dream Engine<br/>(Simulation)"]
        SEARCH["🔍 Web Search<br/>(DuckDuckGo)"]
        LEARN["📊 Learning Engine<br/>(Bayesian)"]
        RESULT["✅ Result Tracker<br/>(Auto-Settle)"]
    end
    style BG fill:#374151,stroke:#9CA3AF,stroke-width:2px,color:#F9FAFB
    HEART --> DREAM --> SEARCH
    ORCH --> LEARN & RESULT

    %% ─── EXTERNAL ───
    subgraph EXT["🌐 External Services"]
        TELE["Telegram Bot"]
        DDG["DuckDuckGo API"]
    end
    style EXT fill:#1F2937,stroke:#6B7280,stroke-width:1px,color:#D1D5DB
    NOTIF --> TELE
    SEARCH --> DDG

    %% ─── CONNECTIONS ───
    HUD --> SB
    TELE -.-> ORCH

---

## Docker 3-Container Architecture

```mermaid
%%{
  init: {
    'theme': 'base',
    'themeVariables': {
      'primaryColor': '#1E3A5F',
      'primaryTextColor': '#FFF',
      'primaryBorderColor': '#2563EB',
      'lineColor': '#94A3B8'
    }
  }
}%%
graph LR
    subgraph DOCKER["🐳 Docker Compose — 3-Container Architecture"]
        direction LR

        subgraph BOT["Strike Bot 🖥️"]
            direction TB
            API["FastAPI Server<br/>Port: 8000"]
            SWAGGER["📘 Swagger: /docs"]
            AGENT["/api/agent"]
            BETTING["/api/betting"]
            BOT_APPS["/api/betting/history<br/>/api/betting/account-summary"]
        end
        style BOT fill:#064E3B,stroke:#10B981,stroke-width:2px,color:#D1FAE5

        subgraph OLLAMA["Ollama 🤖"]
            direction TB
            LLM_LOCAL["Local LLMs<br/>Port: 11434"]
            M1["racing_llama"]
            M2["racing_qwen"]
            M3["func_gemma"]
            M4["lfm_racing"]
            M5["ds_racing"]
        end
        style OLLAMA fill:#4C1D95,stroke:#8B5CF6,stroke-width:2px,color:#EDE9FE

        subgraph MONITOR["Odds Monitor 👁️"]
            direction TB
            SCRAPER["Playwright Scraper"]
            CPU["CPU: 0.8 core"]
            RAM["RAM: 1.5 GB"]
        end
        style MONITOR fill:#78350F,stroke:#F59E0B,stroke-width:2px,color:#FEF3C7
    end
    style DOCKER fill:#0F172A,stroke:#475569,stroke-width:2px,color:#E2E8F0

    BOT <--> OLLAMA
    BOT <--> MONITOR
    BOT --- SHARED["📁 Shared Volume: /app"]
    OLLAMA --- GPU["🎮 WSL2 Intel GPU"]
    MONITOR --- NET["🌐 Bridge Network"]
```

---

## Skill Architecture

### Race Analysis Skill

```
core_agent/skills/race_analysis/
├── __init__.py
├── analyzer.py          # Core value bet engine
└── form_analyzer.py     # Form-based probability estimation

Key Classes:
- RaceAnalyzer: Main analysis engine
- ValueBet: Value bet data structure
- FormAnalyzer: Form parsing and rating
```

**Value Bet Algorithm:**

```python
1. Calculate Implied Probability = 1 / Decimal Odds
2. Get Estimated Probability from form analysis
3. Calculate Edge = Estimated - Implied
4. If Edge >= 5%:
   a. Calculate Kelly Stake = (bp - q) / b
   b. Apply Half-Kelly for safety
   c. Cap at 5% of bankroll
   d. Return ValueBet
```

### Bankroll Governor Skill

```
core_agent/skills/bankroll_manager/
├── __init__.py
└── governor.py          # Bankroll discipline enforcement

Key Classes:
- BankrollGovernor: Main controller
- BetRecord: Individual bet tracking
- DailyStats: Daily aggregation
```

**Discipline Rules:**

```python
HARD_LIMITS = {
    "max_bet_percent": 5.0,      # Never >5% on single bet
    "daily_loss_limit": 20.0,    # Stop after 20% loss
    "max_drawdown": 50.0,        # Stop if down 50% from peak
    "min_edge": 5.0,             # Only bet with 5%+ edge
}
```

### Model Pipeline (AI Agents)

```
core_agent/agents/
├── ai_pydantic.py         # UnifiedOrchestrator + ModelPipeline
├── ai_providers.py       # AI provider routing
├── intent_classifier.py  # Regex-based intent detection
└── specialists/          # Specialist agents
    ├── analyst_agent.py
    ├── scanner_agent.py
    └── bankroll_agent.py
```

**Model Specialties:**

| Model | Role | Specialty | Fallback |
|-------|------|-----------|----------|
| `racing_llama` | Router | Fast reads, synthesis | → `racing_qwen` |
| `racing_qwen` | Fast reads | Balance, odds, status | → `local:llama3.2:1b` |
| `func_gemma` | Write ops | Record, update bets | → Groq cloud |
| `lfm_racing` | Deep analysis | Race evaluation, daily scan | → Gemini cloud |
| `ds_racing` | Reasoning | Probability edge calc | → `kimi-k2.5:cloud` |

---

## Data Flow

### Daily Scan Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│ Scheduler│────▶│  Scraper │────▶│ Analyzer │────▶│ Telegram │
│  (11:00) │     │(TAB4Rac- │     │(Value   │     │ (Notify) │
│          │     │  ing)    │     │  Engine) │     │          │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                 │
                      ▼                 ▼
                ┌──────────┐      ┌──────────┐
                │  HTML    │      │ Form     │
                │  Parse   │      │ Analysis │
                └──────────┘      └──────────┘
```

### Bet Placement Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  User    │────▶│Governor │────▶│ Validate │────▶│  Record  │
│  Input   │     │ Check    │     │  Rules   │     │   Bet    │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                        │
                                        ▼
                                  ┌──────────┐
                                  │ Telegram │
                                  │ Confirm  │
                                  └──────────┘
```

### AI Pipeline Flow

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│User Message │───▶│   Intent    │───▶│   Direct    │───▶│  Response   │
│             │    │Classifier  │    │   Tools     │    │             │
│"balance?"   │    │  (~0ms)    │    │ (Python)    │    │  Synthesis  │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
                                              │
                                              ▼
                   ┌─────────────┐    ┌─────────────┐
                   │  Fallback   │    │   Memory    │
                   │   LLM       │    │  Grounding │
                    │  (Ollama)   │    │  (ChromaDB + Honcho) │
                   └─────────────┘    └─────────────┘
```

---

## Configuration System

### Centralized Model Config

```python
# core_agent/config/model_config.py
class ModelConfig:
    """All model assignments driven by .env"""
    
    # Orchestrator (Groq free tier)
    ORCHESTRATOR = os.getenv("MODEL_ORCHESTRATOR", "local:llama3.2:1b")
    
    # Local models (Ollama)
    REASONER = os.getenv("MODEL_REASONER", "ds_racing")
    SCRAPER = os.getenv("MODEL_SCRAPER", "racing_qwen")
    FUNC_CALL = os.getenv("MODEL_FUNC_CALL", "func_gemma")
    THINKING = os.getenv("MODEL_THINKING", "lfm_racing")
    
    # Embedding model (Ollama local, used by ChromaDB)
    EMBEDDER = os.getenv("MODEL_EMBEDDER", "embeddinggemma:300m")
    
    # Cloud fallbacks
    CLOUD_FALLBACK = os.getenv("MODEL_CLOUD_FALLBACK", "kimi-k2.5:cloud")
```

### Bankroll Configuration

```python
# core_agent/config/settings.py
@dataclass
class BankrollConfig:
    total_bankroll: float = 1000.0
    max_bet_percent: float = 5.0
    daily_loss_limit: float = 20.0
    min_edge_threshold: float = 5.0
    kelly_fraction: float = 0.5
```

### Track Configuration

```python
TRACKS = {
    "turffontein": {
        "name": "Turffontein Racecourse",
        "location": "Johannesburg",
        "surface": "grass",
        "tab_code": "TUR",
        "racing_days": ["Saturday"],
        "url": "https://www.tab4racing.com/racecards/turffontein"
    },
    # ... more tracks
}
```

---

## Storage

### File Structure

```
data/
├── bankroll_state.json       # Current bankroll, peak, P&L
├── bet_history.json          # All bets (open and settled)
├── parser_config.json        # Selector success rates
├── market_snapshot_latest.json # Live odds snapshot
└── daily_scan_YYYY-MM-DD.json # Historical scan results
```

### Bet Record Schema

```json
{
  "bet_id": "20240309120045_SPE",
  "timestamp": "2024-03-09T12:00:45",
  "date": "2024-03-09",
  "track": "Turffontein",
  "race_number": 3,
  "horse": "Speedy Gonzales",
  "odds": 6.5,
  "stake": 50.0,
  "potential_return": 325.0,
  "status": "PENDING",
  "edge_percent": 15.2,
  "confidence": "STRONG_VALUE"
}
```

---

## Security Considerations

### Credentials
- Stored in `.env` (gitignored)
- Never committed to repository
- Loaded via environment variables

### Data Protection
- User data stored locally + optionally in ChromaDB Cloud
- ChromaDB Cloud for persistent memory (requires CHROMA_API_KEY)
- Embedding models: Ollama local (embeddinggemma:300m) → Gemini cloud fallback → ChromaDB default
- No external APIs except Telegram/Groq/Gemini/ChromaDB Cloud

### Betting Safety
- Hard-coded limits (5% max, 20% daily loss)
- Cannot be overridden via config
- Requires code change to modify

---

## Extensibility

### Adding New Data Sources

```python
# core_agent/skills/parsers/new_source.py
class NewSourceScraper:
    def scrape_racecard(self, track: str) -> List[ScrapedRace]:
        # Implementation
        pass

# In core_agent/core/strike_tips.py
from core_agent.skills.parsers.new_source import NewSourceScraper

class StrikeTips:
    def __init__(self):
        self.scrapers = [
            TAB4RacingScraper(),
            NewSourceScraper(),  # Add here
        ]
```

### Adding New AI Models

```python
# In .env
MODEL_NEW_MODEL=my-custom-model

# In core_agent/config/model_config.py
NEW_MODEL = os.getenv("MODEL_NEW_MODEL", "default")

# Usage in code
from core_agent.config.model_config import ModelConfig
model = ModelConfig.NEW_MODEL
```

---

## Performance

### Caching Strategy
- Racecards cached per session
- Form data cached per day
- Bankroll state persisted immediately

### Rate Limiting
- Scraper: 1 request per second
- Telegram: Respect API limits
- LLM calls: Timeout at 60s

### Docker Resource Limits

| Container | CPU | Memory |
|-----------|-----|--------|
| strike-bot | 1.0 | 2.0G |
| ollama | 1.5 | 2.5G |
| odds-monitor | 0.8 | 1.5G |

---

## Error Handling

### Scraper Errors
```python
try:
    races = scraper.scrape_racecard(track)
except Exception as e:
    logger.error(f"Scraper failed: {e}")
    if telegram:
        telegram.send_error_notification(str(e), context="Scraping")
```

### LLM Fallback
```python
# Try local Ollama first
response = await self._call_ollama(model, prompt)
if not response:
    # Fall back to Groq
    response = await self._call_groq(prompt)
if not response:
    # Fall back to Gemini
    response = await self._call_gemini(prompt)
```

---

## Development Guidelines

### Adding a New Skill

1. Create directory: `core_agent/skills/new_skill/`
2. Implement core class
3. Add `__init__.py` exports
4. Write tests
5. Update documentation

### Code Style
- Black formatter (88 char line length)
- Type hints required
- Docstrings for all public methods
- Unit tests for core logic
- Docker paths use `/app/` prefix

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | March 2024 | Initial release |
| 2.0 | April 2026 | Refactored to core_agent/, removed Pydantic AI, added Docker 3-container setup |

---

*Architecture Version: 2.0*
*Last Updated: April 2026*
