# 🚀 Getting Started with Strike Tips v2.0

Complete setup guide for South African horse racing enthusiasts.

---

## 📋 Prerequisites

- Python 3.9 or higher
- Docker & Docker Compose
- A Telegram account
- Basic command line knowledge

---

## 🚀 Quick Start (Docker - Recommended)

### Step 1: Clone and Start

```bash
# Clone the repository
git clone https://github.com/yourusername/strike-tips.git
cd strike-tips

# Start all containers
docker compose up -d

# Check status
docker ps
```

### Step 2: Verify Services

```bash
# API should be available
curl http://localhost:8000

# Swagger docs at
# http://localhost:8000/docs

# Ollama health check
curl http://localhost:11434/api/tags
```

### Step 3: Configure Telegram

```bash
# Edit .env file
nano .env
```

Add your credentials:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## 🐳 Docker Architecture

### 3-Container Setup

| Container | Service | Port | Purpose |
|-----------|---------|------|---------|
| `strike-bot` | FastAPI | 8000 | Backend API |
| `ollama` | Local LLM | 11434 | AI models |
| `odds-monitor` | Playwright | - | Live odds scraper + ATR data (Market Movers, Predictor, Results) |

### Common Docker Commands

```bash
# Start all containers
docker compose up -d

# View logs
docker logs -f strike-bot

# Stop all containers
docker compose down

# Restart a specific container
docker restart strike-bot

# Run command in container
docker exec -it strike-bot python core_agent/core/strike_tips.py scan
```

---

## 🔧 Manual Setup (Development)

If you prefer running without Docker:

### Step 1: Install Dependencies

```bash
# Navigate to core_agent
cd core_agent

# Create virtual environment
python -m venv venv

# Activate
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment

```bash
# Copy environment template
cp .env.example .env

# Edit with your settings
nano .env
```

Required variables:
```env
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=your_chat_id
GROQ_API_KEY=your_groq_key
```

### Step 3: Start Ollama (for local AI models)

```bash
# Install and start Ollama
ollama serve

# Pull required models
ollama pull llama3.2:1b
ollama pull racing_llama
ollama pull racing_qwen
```

### Step 4: Run the API

```bash
# In core_agent directory
python api.py

# API available at http://localhost:8000
```

---

## 🧪 Testing Your Setup

### Test 1: API Health

```bash
curl http://localhost:8000
# Expected: {"message":"Strike Bot API Online"}
```

### Test 2: Agent Health

```bash
curl http://localhost:8000/api/agent/health
```

### Test ATR Data Endpoints (New in v2.0)

```bash
# ATR Market Movers (523+ items)
curl http://localhost:8000/api/racing/market-movers

# ATR Predictor (39+ predictions)
curl http://localhost:8000/api/racing/predictor

# ATR Results (579+ results)
curl http://localhost:8000/api/racing/results
```

### Test 3: Telegram

```bash
# Inside container
docker exec -it strike-bot python -c "
from core_agent.skills.notifications.telegram_bot import TelegramNotifier
notifier = TelegramNotifier()
notifier.send_message('Test from Strike Tips!')
"
```

### Test MAF Tools (15 tools available)

```bash
# List all tools
curl http://localhost:8000/api/agent/tools

# Test ATR tools
curl -X POST http://localhost:8000/api/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Show me ATR market movers"}'
```

---

## 🏇 Running Your First Scan

### Via Docker

```bash
# Run daily scan
docker exec -it strike-bot python core_agent/core/strike_tips.py scan
```

### Via API

```bash
curl -X POST http://localhost:8000/api/agent/scan
```

### Via Swagger UI

1. Open http://localhost:8000/docs
2. Find `/api/agent/chat` endpoint
3. Send message: "What races are on today?"

---

## 📊 Understanding the Output

### Telegram Messages

#### Daily Tips Summary

```
🏇 STRIKE TIPS - Daily Racing Tips
📅 Saturday, 09 March 2024

📍 Turffontein: 7 races, 3 value bets
📍 Kenilworth: 8 races, 2 value bets

━━━━━━━━━━━━━━━━━━━━━
📊 Total: 6 value bets identified today
```

#### Value Bet Alert

```
🔥 STRIKE TIPS - VALUE BET

📍 Turffontein - Race 3 (14:30)
🐎 Speedy Gonzales
💰 Odds: 6.5 | Edge: +15.2%
💵 Advised Stake: R50.00
📊 Confidence: STRONG_VALUE

📝 Analysis:
Recent form: 1-2-1 | Proven at track/distance

⚠️ Bet responsibly. Max 5% per bet rule applied.
```

### Key Terms

| Term | Meaning |
|------|---------|
| **Edge** | Your estimated probability minus market implied probability |
| **Kelly** | Optimal stake percentage based on edge and odds |
| **Confidence** | STRONG_VALUE (>15%), VALUE (5-15%), MARGINAL (3-5%) |
| **Stake** | Recommended bet amount (capped at 5% of bankroll) |

---

## 💰 Managing Your Bankroll

### Check Status

```bash
# Via API
curl http://localhost:8000/api/agent/chat \
  -X POST -H "Content-Type: application/json" \
  -d '{"message": "What is my balance?"}'
```

### Record a Bet

```bash
# Via API
curl http://localhost:8000/api/agent/chat \
  -X POST -H "Content-Type: application/json" \
  -d '{"message": "Record R50 on Speedy Gonzales at 6.5 odds"}'
```

---

## ⚙️ Customization

### Adjust Risk Tolerance

Edit `core_agent/config/settings.py`:

```python
@dataclass
class BankrollConfig:
    total_bankroll: float = 1000.0
    max_bet_percent: float = 3.0    # More conservative (was 5%)
    daily_loss_limit: float = 15.0   # Stop earlier (was 20%)
    min_edge_threshold: float = 8.0  # Require higher edge (was 5%)
    kelly_fraction: float = 0.25     # Quarter-Kelly (was 0.5)
```

### Model Configuration

Edit `.env`:

```env
MODEL_REASONER=ds_racing
MODEL_SCRAPER=racing_qwen
MODEL_THINKING=lfm_racing
MODEL_FUNC_CALL=func_gemma
```

---

## 🔧 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs strike-bot

# Check if port is in use
netstat -tuln | grep 8000

# Restart Docker
systemctl restart docker
```

### Ollama Not Working

```bash
# Check Ollama logs
docker logs ollama

# Test Ollama directly
curl http://localhost:11434/api/tags

# Restart Ollama container
docker restart ollama
```

### Telegram Not Working

```bash
# Test inside container
docker exec -it strike-bot python -c "
from core_agent.skills.notifications.telegram_bot import TelegramNotifier
n = TelegramNotifier()
print('Token:', n.bot_token[:10] + '...')
"
```

### Scraper Not Finding Data

```bash
# Test scraper
docker exec -it strike-bot python -c "
from core_agent.skills.parsers.tab4racing import TAB4RacingScraper
s = TAB4RacingScraper()
html = s._get('/racecards/turffontein')
print('Success!' if html else 'Failed')
"
```

---

## 📚 Next Steps

1. **Explore the API**: http://localhost:8000/docs
2. **Read the Architecture**: [docs/ARCHITECTURE.md](ARCHITECTURE.md)
3. **Review Agent Guidelines**: [docs/AGENTS.md](AGENTS.md)
4. **Check the Model Pipeline**: [docs/MAF Framework.md](MAF%20Framework.md)

---

## 🆘 Getting Help

- **GitHub Issues**: Report bugs and feature requests
- **Telegram**: @StrikeTipsSupport

---

**Happy punting! 🏇**

Remember: Bet smart, bet disciplined, and never bet more than you can afford to lose.

---

*Last Updated: April 2026*
*Version: 2.0*