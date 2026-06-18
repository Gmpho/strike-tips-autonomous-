# How to Bet — Strike Tips Racing Bot

**Effective Date:** June 2026  
**Version:** 1.0  
**Jurisdiction:** South Africa

---

## 1. Overview

Strike Tips Racing Bot is a **paper-trading educational system** — it simulates betting selections against a virtual bankroll (starting at R1,000 ZAR). No real money is ever wagered, collected, or paid out.

This guide explains how the system generates selections and how to interpret the output for learning purposes.

---

## 2. What You'll See

### Daily Race Analysis
- **Race cards** for South African tracks (Turffontein, Vaal, Fairview, Scottsville, Kenilworth, Durbanville, Greyville)
- **AI analysis** from a multi-agent swarm (5 local models + cloud fallback)
- **Edge calculations** — probability vs. market odds
- **Simulated stake suggestions** — Kelly fraction (half-Kelly for safety)

### Selection Format
Each selection shows:
```
Horse Name | Track Race# | Odds | Edge % | Stake (R) | Confidence
```

---

## 3. How the System Works

### 3.1 Data Pipeline
1. **Scrapers** fetch race cards & odds from TAB4Racing, Betway, Racing Post
2. **Form Analyzer** evaluates horse/jockey/trainer stats, track conditions, distance suitability
3. **Edge Calculator** compares implied probability vs. model probability
4. **Bankroll Governor** applies Kelly criterion with 5% max bet, 20% daily loss limit
5. **Result Tracker** auto-settles after races (DuckDuckGo search → scrape → fuzzy match)

### 3.2 AI Agent Swarm
| Model | Role | Specialty |
|-------|------|-----------|
| `racing_llama` | Router + Synthesizer | Fast, all tools |
| `racing_qwen` | Fast Reads | Account summary, search |
| `func_gemma` | Write Ops | Record selections, update results |
| `lfm_racing` | Deep Analysis | Race evaluation, daily scan |
| `ds_racing` | Reasoning | Probability edge calculation |
| Groq Llama 3.3 70B | Cloud fallback | Complex reasoning |
| Gemini 2.0 Flash | Cloud fallback | Speed |

---

## 4. Interpreting Output

### Key Metrics
- **Edge %** = (Model Probability × Decimal Odds) − 1
- **Stake** = Bankroll × Kelly Fraction × Edge (capped at 5%)
- **Confidence** = High / Medium / Low based on data quality

### Example
```
Reflective | Vaal R8 | 5.50 | +12.4% | R42 | HIGH
```
→ Model gives 20.4% win probability vs. market 18.2% (5.50 odds)  
→ Kelly stake = R1,000 × 0.5 × 0.124 = R62 → capped at 5% = R50 → R42 after rounding

---

## 5. Telegram Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome + PIN prompt |
| `/races` | Today's race cards |
| `/selections` | Current paper-trading picks |
| `/bankroll` | Virtual balance & P&L |
| `/results` | Settled results (today) |
| `/stats` | ROI, strike rate, best tracks |
| `/help` | Command list |

---

## 6. Web Dashboard (HUD)

Visit `https://strike-tips-hud.vercel.app` for:
- Live race cards with AI selections
- Bankroll history chart
- Agent pipeline status
- Market movers & ATR predictors
- System vitals & logs

---

## 7. Important Reminders

⚠️ **PAPER TRADING ONLY** — No real money involved  
⚠️ **Simulated results ≠ real-world outcomes**  
⚠️ **Not financial or betting advice**  
✅ **Educational use only** — learn racing analysis, bankroll discipline, edge identification

---

## 8. Responsible Gambling

If you choose to bet real money elsewhere:

| Resource | Contact |
|----------|---------|
| National Responsible Gambling Programme | **0800 006 008** (24/7 toll-free) |
| WhatsApp Support | **'HELP' to 076 675 0710** |
| Website | `responsiblegambling.org.za` |

**Warning signs:** Chasing losses, betting beyond means, hiding activity, borrowing to bet.

---

## 9. Contact

**System Administrator:** Telegram `@StrikeTipsBot` (send `/help`)  
**Regulator Reference:** Mpumalanga Economic Regulator