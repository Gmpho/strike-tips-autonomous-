# Disclaimer — Strike Tips Racing Bot

**Last Updated:** June 2026  
**Version:** 1.0

---

## 📢 PAPER TRADING ONLY — NO REAL MONEY

**Every figure, result, "win," "loss," "bankroll," "ROI," "profit," "stake," and "payout" shown by this system is SIMULATED.**

- **Starting virtual bankroll:** R1,000 ZAR (fake money)
- **All bets:** Paper trades — no actual wagers placed
- **All outcomes:** Simulated for educational demonstration
- **No real money is ever:** Deposited, wagered, won, lost, or withdrawn

**Do not use this system's output to make real-money betting decisions.**

---

## 🎯 What This System Actually Does

Strike Tips Racing Bot is an **educational intelligence platform** that:

1. **Scrapes public race data** from TAB4Racing, Betway, and Racing Post
2. **Analyzes form, odds, and conditions** using a multi-agent AI swarm
3. **Simulates paper-trading selections** against a virtual R1,000 bankroll
4. **Tracks simulated performance** (ROI, P&L, strike rate) over time
5. **Delivers insights** via Telegram and a web dashboard (HUD)

**Architecture:** 5 specialized local models (Ollama) + cloud fallback (Groq Llama 3.3 70B, Gemini 2.0 Flash) orchestrated via intent routing with ChromaDB + Honcho dual memory.

---

## ⚠️ Key Warnings

### Simulated Results ≠ Real-World Outcomes
- Paper trading has **no financial risk** — real betting does
- Simulated ROI (e.g., "104.4% ROI" or "R1,000 → R2,255.46") **does not predict** actual betting returns
- Market conditions, liquidity, bookmaker limits, and psychology differ entirely from simulation

### Not Financial Advice
- This system provides **racing analysis and education**, not investment advice
- No agent, model, or output constitutes a recommendation to bet real money
- Consult a licensed financial advisor for financial decisions

### Not a Gambling Service
- We are **not a bookmaker**, **not a betting platform**, **not a tipster service**
- No license from any gambling regulator for real-money operations
- No affiliation with Betway, TAB, Hollywoodbets, or any operator

### Data Sources Are Third-Party
- Odds and race data come from **Betway**, **TAB4Racing**, **Racing Post**
- We do not control their accuracy, availability, or terms of use
- Scraping is for **informational paper-trading purposes only**

---

## 🛡️ Responsible Gambling

**If you choose to bet real money elsewhere:**

| Resource | Contact |
|---|---|
| **National Responsible Gambling Programme (SA)** | **0800 006 008** (24/7 toll-free) |
| **WhatsApp Support** | **'HELP' to 076 675 0710** |
| **Website** | `https://www.responsiblegambling.org.za` |

**Warning signs:** Chasing losses, betting beyond means, hiding betting, borrowing to bet, emotional distress.

**Self-exclusion:** Register with the **National Central Electronic Monitoring System (NCEMS)** via your bookmaker.

---

## 🏛️ Regulatory Context

- **South Africa:** Gambling Act 2004, Provincial Gambling Boards, POPIA
- **This system:** Paper-trading educational tool — not regulated as gambling
- **Regulator referenced:** Mpumalanga Economic Regulator
- **Age restriction:** 18+ only (enforced via `BOT_ACCESS_PIN`)

---

## 🤖 AI & Model Limitations

- **Local models** (Ollama): `racing_llama`, `racing_qwen`, `func_gemma`, `lfm_racing`, `ds_racing`
- **Cloud fallback:** Groq (Llama 3.3 70B), Google (Gemini 2.0 Flash)
- **Hallucination risk:** AI can generate incorrect analysis — verify independently
- **No model** has access to real-time bookmaker accounts or insider information

---

## 📊 Performance Claims

Any performance metrics displayed (ROI %, profit/loss, strike rate, edge %) are:
- **Historical paper-trading simulations only**
- **Backtested on past races** with known outcomes
- **Subject to look-ahead bias, survivorship bias, and overfitting**
- **Not audited, not verified, not guaranteed**

**Format for all metrics:** `[PAPER MODE] Simulated: ROI +104.4% | Bankroll R1,000 → R2,255.46`

---

## 🔗 Related Documents

- [Privacy Policy](PRIVACY.md) — POPIA-compliant data handling
- [Terms of Service](TERMS.md) — Free educational service terms

---

## 📞 Contact

**System Administrator:** Telegram `@StrikeTipsBot` (send `/disclaimer`)  
**Responsible Gambling:** 0800 006 008 | WhatsApp 'HELP' to 076 675 0710

---

**By using Strike Tips Racing Bot, you acknowledge:**
1. ✅ This is paper trading only — no real money involved
2. ✅ Simulated results do not predict real-world outcomes
3. ✅ This is not financial or betting advice
4. ✅ You are 18+ and located where legal
5. ✅ You will not hold the system liable for any decisions you make