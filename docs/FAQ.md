# Frequently Asked Questions — Strike Tips Racing Bot

**Last Updated:** June 2026  
**Version:** 1.0

---

## General

### What is Strike Tips Racing Bot?
An educational paper-trading system for South African horse racing that uses AI to analyze races, calculate edges, and simulate selections against a virtual R1,000 bankroll. No real money is involved.

### Is this a betting platform?
**No.** It's a learning tool. No bets are placed, no money is deposited/withdrawn, no odds are offered for real wagering.

### Who can use it?
Adults (18+) in South Africa (or jurisdictions where accessing racing data is legal). Access requires the `BOT_ACCESS_PIN`.

### How much does it cost?
**Free.** No subscription, no premium tiers, no payment details collected.

---

## Technical

### Which AI models does it use?
- **Local (Ollama):** `racing_llama`, `racing_qwen`, `func_gemma`, `lfm_racing`, `ds_racing`
- **Cloud fallback:** Groq (Llama 3.3 70B), Google (Gemini 2.0 Flash)

### Where does race data come from?
Public sources: TAB4Racing, Betway, Racing Post. Scraped for informational paper-trading purposes only.

### How is my data stored?
- **Telegram:** Messages, user ID, chat ID
- **ChromaDB Cloud:** Vector embeddings of conversations
- **Honcho:** Session memory
- **Redis:** Caching, queues
- **Local:** Ollama runs on your infrastructure (no data leaves for local inference)

### Is my data private?
Yes. POPIA-compliant. No marketing, no data sales. See [Privacy Policy](/privacy).

---

## Paper Trading

### What's the starting bankroll?
R1,000 ZAR (virtual/fake money).

### How are stakes calculated?
Half-Kelly criterion: `Stake = Bankroll × 0.5 × Edge`, capped at 5% of bankroll per bet.

### How are results settled?
Automatically via `ResultTracker`: searches DuckDuckGo for results → scrapes → fuzzy matches winner → updates virtual P&L.

### Can I reset my bankroll?
Yes, via Settings in the HUD or `/config` API.

---

## Telegram Bot

### How do I start?
Message `@StrikeTipsBot` on Telegram, enter the `BOT_ACCESS_PIN` when prompted.

### What commands are available?
`/start`, `/races`, `/selections`, `/bankroll`, `/results`, `/stats`, `/help`, `/privacy`, `/terms`, `/disclaimer`

### Why do messages say `[PAPER MODE]`?
Every message is prefixed to reinforce: **no real money is ever wagered**.

---

## Troubleshooting

### Bot not responding?
- Check PIN is correct
- Ensure `TELEGRAM_MODE=webhook` or `polling` is set
- Check bot token is valid

### No races showing?
- Racing days vary by track (see tracks table in code)
- Scrapers run on schedule; wait for next cycle

### HUD not loading data?
- Ensure backend is running on port 8000
- Check CORS allows `localhost:5173`
- Verify `STRIKE_TIPS_API_KEY` matches

---

## Legal

### Is this legal?
Yes — paper-trading educational tool under South African law. Not a gambling service.

### Which regulator?
Referenced: Mpumalanga Economic Regulator.

### Where are full terms?
[Terms of Service](/terms) | [Privacy Policy](/privacy) | [Disclaimer](/disclaimer)

---

## Contact

**System Administrator:** Telegram `@StrikeTipsBot`  
**Responsible Gambling:** 0800 006 008 | WhatsApp 'HELP' to 076 675 0710