# 🚀 Getting Started with Strike Tips

Complete setup guide for South African horse racing enthusiasts.

---

## 📋 Prerequisites

- Python 3.9 or higher
- A Telegram account
- Basic command line knowledge

---

## Step 1: Installation

### Clone and Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/strike-tips.git
cd strike-tips

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On macOS/Linux:
source venv/bin/activate
# On Windows:
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

---

## Step 2: Telegram Bot Setup

### Create Your Bot

1. Open Telegram and search for **@BotFather**
2. Start a chat and type `/newbot`
3. Follow prompts to name your bot (e.g., "StrikeTipsBot")
4. **Save the bot token** - you'll need it!

### Get Your Chat ID

1. Search for **@userinfobot** on Telegram
2. Start the bot
3. It will reply with your Chat ID
4. **Save this number**

### Configure Environment

```bash
# Copy the example environment file
cp .env.example .env

# Edit the file
nano .env  # or use your preferred editor
```

Add your credentials:

```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrSTUvwxyz
TELEGRAM_CHAT_ID=123456789
```

---

## Step 3: Test Your Setup

```bash
# Test Telegram connection
python scheduler.py test
```

You should receive a test message in Telegram!

---

## Step 4: Run Your First Scan

```bash
# Run immediate scan
python scheduler.py scan
```

This will:
1. Check which tracks are racing today
2. Scrape racecards from TAB4Racing
3. Analyze each race for value bets
4. Send results to Telegram

---

## Step 5: Set Up Automation

### Option A: Run Scheduler (Recommended)

```bash
# Start automated daily scans at 11:00 AM
python scheduler.py start

# Or specify a different time
python scheduler.py start --time 10:30
```

The scheduler will:
- Run daily at your specified time
- Automatically detect racing tracks
- Send tips to Telegram
- Track your bankroll

### Option B: Cron Job (Linux/Mac)

```bash
# Edit crontab
crontab -e

# Add line for daily scan at 11:00 AM
0 11 * * * cd /path/to/strike-tips && /path/to/venv/bin/python scheduler.py scan
```

### Option C: Windows Task Scheduler

1. Open Task Scheduler
2. Create Basic Task
3. Set trigger: Daily at 11:00 AM
4. Set action: Start a program
5. Program: `python.exe`
6. Arguments: `scheduler.py scan`
7. Start in: `C:\path\to\strike-tips`

---

## 📊 Understanding the Output

### Telegram Messages

#### Daily Tips Summary

```
🏇 STRIKE TIPS - Daily Racing Tips
📅 Saturday, 09 March 2024

📍 Turffontein: 7 races, 3 value bets
📍 Kenilworth: 8 races, 2 value bets
📍 Flamingo: 6 races, 1 value bet

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

### Initial Setup

Default starting bankroll is R1,000. To change:

```python
# In config/settings.py or via environment
STARTING_BANKROLL=2000
```

### Tracking Bets

```bash
# Check current status
python strike_tips.py status

# Output:
{
  "current_bankroll": 950.00,
  "peak_bankroll": 1000.00,
  "total_profit_loss": -50.00,
  "drawdown_percent": 5.0,
  "open_bets": 2
}
```

### Recording Bets Manually

```bash
# Place a bet
python strike_tips.py bet \
    --track turffontein \
    --race 3 \
    --horse "Speedy Gonzales" \
    --odds 6.5 \
    --edge 15.2

# Settle a bet (when you know the result)
python strike_tips.py settle --bet-id 20240309120045_SPE --won
```

### Daily Report

```bash
python strike_tips.py report
```

---

## ⚙️ Customization

### Adjust Risk Tolerance

Edit `config/settings.py`:

```python
@dataclass
class BankrollConfig:
    total_bankroll: float = 1000.0
    max_bet_percent: float = 3.0    # More conservative (was 5%)
    daily_loss_limit: float = 15.0   # Stop earlier (was 20%)
    min_edge_threshold: float = 8.0  # Require higher edge (was 5%)
    kelly_fraction: float = 0.25     # Quarter-Kelly (was 0.5)
```

### Add Custom Tracks

```python
# In config/settings.py
TRACKS = {
    "my_track": {
        "name": "My Track",
        "location": "City",
        "url": "https://..."
    }
}
```

---

## 🔧 Troubleshooting

### Telegram Not Working

```bash
# Test connection
python scheduler.py test

# Common issues:
# 1. Wrong bot token format
# 2. Chat ID is a number, not username
# 3. Haven't started chat with bot
```

### Scraper Not Finding Data

```bash
# Check if TAB4Racing is accessible
python -c "
from skills.parsers.tab4racing import TAB4RacingScraper
scraper = TAB4RacingScraper()
html = scraper._get('/racecards/turffontein')
print('Success!' if html else 'Failed')
"
```

### Reset Everything

```bash
# WARNING: This deletes all data!
make reset-data

# Or manually:
rm data/*.json
```

---

## 📚 Next Steps

1. **Read the full documentation**: [README.md](README.md)
2. **Explore examples**: `examples/quick_start.py`
3. **Run tests**: `make test`
4. **Join the community**: [Telegram Group](https://t.me/striketips)

---

## 🆘 Getting Help

- **GitHub Issues**: Report bugs and feature requests
- **Telegram**: @StrikeTipsSupport
- **Email**: support@striketips.co.za

---

**Happy punting! 🏇**

Remember: Bet smart, bet disciplined, and never bet more than you can afford to lose.
