# Strike Tips - Architecture Documentation

## System Overview

Strike Tips is built on a modular skill-based architecture inspired by agent systems. Each skill is self-contained and can operate independently.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STRIKE TIPS SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ORCHESTRATOR                                 │   │
│  │                      (strike_tips.py)                               │   │
│  │                                                                     │   │
│  │  • Coordinates all skills                                          │   │
│  │  • Manages data flow                                                │   │
│  │  • Handles CLI interface                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐        │
│  │   RACE      │          │  BANKROLL   │          │ NOTIFICATIONS│        │
│  │  ANALYSIS   │          │   GOVERNOR  │          │  (Telegram)  │        │
│  │   SKILL     │          │   SKILL     │          │    SKILL     │        │
│  ├─────────────┤          ├─────────────┤          ├─────────────┤        │
│  │ • Value     │          │ • Max 5%   │          │ • Daily     │        │
│  │   Engine    │          │   Rule     │          │   Tips      │        │
│  │ • Kelly     │          │ • Loss     │          │ • Bet       │        │
│  │   Staking   │          │   Limits   │          │   Alerts    │        │
│  │ • Form      │          │ • P&L      │          │ • Results   │        │
│  │   Analysis  │          │   Track    │          │ • Bankroll  │        │
│  │             │          │ • Kelly    │          │   Updates   │        │
│  │             │          │   Sizing   │          │             │        │
│  └─────────────┘          └─────────────┘          └─────────────┘        │
│         │                          │                          │            │
│         └──────────────────────────┼──────────────────────────┘            │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                   MODEL PIPELINE LAYER (AI AGENTS)                 │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐ │   │
│  │  │  racing_llama (Router) → Specialist → Synthesizer            │ │   │
│  │  └─────────────────────────────────────────────────────────────┘ │   │
│  │                                                                     │   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │   │
│  │  │ racing_qwen   │  │  func_gemma   │  │  lfm_racing   │      │   │
│  │  │  Fast Reads   │  │ Write Ops    │  │ Deep Analysis │      │   │
│  │  │  (~1-2s)     │  │  (~1-2s)     │  │  (~2-3s)     │      │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐        │
│  │   Learning  │          │    Result   │          │   Memory    │        │
│  │   Engine   │          │   Tracker   │          │ (ChromaDB) │        │
│  │  skills/   │          │ skills/     │          │  skills/    │        │
│  │  learning/ │          │result_track │          │   memory/   │        │
│  └─────────────┘          └─────────────┘          └─────────────┘        │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     DATA INGESTION LAYER                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐      │   │
│  │  │ TAB4Racing    │  │ DuckDuckGo   │  │ StealthEngine │      │   │
│  │  │ Scraper       │  │ Search       │  │ (Bypass bans) │      │   │
│  │  └───────────────┘  └───────────────┘  └───────────────┘      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STRIKE TIPS SYSTEM                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        ORCHESTRATOR                                 │   │
│  │                      (strike_tips.py)                               │   │
│  │                                                                     │   │
│  │  • Coordinates all skills                                          │   │
│  │  • Manages data flow                                                │   │
│  │  • Handles CLI interface                                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│         ┌──────────────────────────┼──────────────────────────┐            │
│         │                          │                          │            │
│         ▼                          ▼                          ▼            │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐        │
│  │   RACE      │          │  BANKROLL   │          │ NOTIFICATIONS│        │
│  │  ANALYSIS   │          │   GOVERNOR  │          │  (Telegram)  │        │
│  │   SKILL     │          │   SKILL     │          │    SKILL     │        │
│  ├─────────────┤          ├─────────────┤          ├─────────────┤        │
│  │             │          │             │          │             │        │
│  │ • Value     │          │ • Max 5%   │          │ • Daily     │        │
│  │   Engine    │          │   Rule     │          │   Tips      │        │
│  │ • Kelly     │          │ • Loss     │          │ • Bet       │        │
│  │   Staking   │          │   Limits   │          │   Alerts    │        │
│  │ • Form      │          │ • P&L      │          │ • Results   │        │
│  │   Analysis  │          │   Track    │          │ • Bankroll  │        │
│  │             │          │ • Kelly    │          │   Updates   │        │
│  │             │          │   Sizing   │          │             │        │
│  └─────────────┘          └─────────────┘          └─────────────┘        │
│         │                          │                          │            │
│         └──────────────────────────┼──────────────────────────┘            │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     DATA INGESTION LAYER                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐      │   │
│  │  │ TAB4Racing    │    │ Self-Healing  │    │ Form Database │      │   │
│  │  │ Scraper       │    │ Parser        │    │ (Future)      │      │   │
│  │  ├───────────────┤    ├───────────────┤    ├───────────────┤      │   │
│  │  │ • Turffontein │    │ • Adaptive    │    │ • Historical  │      │   │
│  │  │ • Kenilworth  │    │   Selectors   │    │   Results     │      │   │
│  │  │ • Vaal        │    │ • Fallback    │    │ • Jockey/     │      │   │
│  │  │ • Greyville   │    │   Strategies  │    │   Trainer     │      │   │
│  │  │ • Fairview    │    │ • Auto-Patch  │    │   Stats       │      │   │
│  │  │ • Flamingo    │    │   Generation  │    │               │      │   │
│  │  └───────────────┘    └───────────────┘    └───────────────┘      │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                      CONFIGURATION LAYER                            │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │  • settings.py - All configuration                                  │   │
│  │  • .env - Environment variables (credentials)                       │   │
│  │  • Tracks, bankroll rules, scraper settings                         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Skill Architecture

### Race Analysis Skill

```
skills/race_analysis/
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
skills/bankroll_manager/
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

### Notification Skill

```
skills/notifications/
├── __init__.py
└── telegram_bot.py      # Telegram integration

Key Classes:
- TelegramNotifier: Bot interface
```

**Message Types:**
- Daily Tips Summary
- Value Bet Alerts
- Bet Confirmations
- Race Results
- Bankroll Updates
- Error Alerts

### Parser Skill

```
skills/parsers/
├── __init__.py
├── tab4racing.py        # Primary SA racing scraper
└── self_healing.py      # Adaptive parser

Key Classes:
- TAB4RacingScraper: Main scraper
- SelfHealingParser: Adaptive selector logic
```

**Self-Healing Mechanism:**

```python
1. Try selectors in order of historical success
2. Track success/fail rates per selector
3. On failure, try fallback strategies
4. Suggest new selectors based on HTML analysis
5. Generate patch code for manual review
```

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

---

## Configuration System

### Hierarchical Config

```python
# 1. Default values (config/settings.py)
@dataclass
class BankrollConfig:
    total_bankroll: float = 1000.0
    max_bet_percent: float = 5.0

# 2. Environment variables (.env)
STARTING_BANKROLL=2000

# 3. Runtime overrides
strike = StrikeTips(bankroll_config=custom_config)
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
- User data stored locally
- No cloud storage
- No external APIs except Telegram

### Betting Safety
- Hard-coded limits (5% max, 20% daily loss)
- Cannot be overridden via config
- Requires code change to modify

---

## Extensibility

### Adding New Data Sources

```python
# skills/parsers/new_source.py
class NewSourceScraper:
    def scrape_racecard(self, track: str) -> List[ScrapedRace]:
        # Implementation
        pass

# In strike_tips.py
from skills.parsers.new_source import NewSourceScraper

class StrikeTips:
    def __init__(self):
        self.scrapers = [
            TAB4RacingScraper(),
            NewSourceScraper(),  # Add here
        ]
```

### Adding New Notification Channels

```python
# skills/notifications/whatsapp.py
class WhatsAppNotifier:
    def send_message(self, text: str):
        # Implementation
        pass

# In strike_tips.py
if enable_whatsapp:
    self.whatsapp = WhatsAppNotifier()
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
- No parallel scraping (sequential)

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

### Parser Errors
```python
# Self-healing parser handles this
result = parser.find_element(soup, "horse_name")
if not result:
    # Try fallback strategies
    result = parser.fallback_strategy(soup)
```

---

## Future Enhancements

### Planned Features
1. Machine learning form analysis
2. Historical odds database
3. Multiple bookmaker comparison
4. Live odds tracking
5. Advanced staking strategies
6. Web dashboard
7. Mobile app

### Integration Points
- Racing Post API
- Betfair API
- Oddschecker
- Weather APIs (track conditions)

---

## Development Guidelines

### Adding a New Skill

1. Create directory: `skills/new_skill/`
2. Implement core class
3. Add `__init__.py` exports
4. Write tests
5. Update documentation

### Code Style
- Black formatter (100 char line length)
- Type hints required
- Docstrings for all public methods
- Unit tests for core logic

---

*Architecture Version: 1.0*
*Last Updated: March 2024*
