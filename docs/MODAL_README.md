# 🚀 Strike Tips on Modal

Deploy Strike Tips on Modal's free tier ($30 credit).

---

## 📋 Quick Deploy (3 Steps)

### 1. Install Modal

```bash
pip install modal
modal setup
```

### 2. Configure Secrets

```bash
python deploy_modal.py
```

This will prompt for:
- **Telegram Bot Token** (required) - Get from [@BotFather](https://t.me/botfather)
- **Telegram Chat ID** (required) - Get from [@userinfobot](https://t.me/userinfobot)
- **AI Provider API Key** (at least one recommended):
  - Gemini API Key (free tier available)
  - Anthropic API Key
  - OpenAI API Key

### 3. Deploy

```bash
modal deploy modal_app.py
```

---

## 💰 Cost Estimation (Free Tier)

Modal's free tier includes:
- **$30/month credit**
- **128 MB RAM** functions
- **Scheduled jobs** (cron)
- **Web endpoints**

### Strike Tips Usage:

| Component | Daily Cost | Monthly Cost |
|-----------|------------|--------------|
| Daily scan (5 min) | ~$0.02 | ~$0.60 |
| AI analysis (Gemini) | Free | Free |
| Telegram notifications | Free | Free |
| **Total** | **~$0.02** | **~$0.60** |

✅ **Well within $30/month free tier!**

---

## 🎯 Usage

### Automatic (Scheduled)

The app runs automatically every day at **11:00 AM SAST**.

### Manual Trigger

```bash
# Run scan manually
modal run modal_app.py::daily_racing_scan

# Or via HTTP POST
curl -X POST <your-web-endpoint-url>
```

### Check Logs

```bash
modal app logs strike-tips
```

---

## 🔧 AI Provider Priority

The app tries AI providers in this order:

1. **Gemini** (recommended - free tier)
2. **Claude** (Haiku - cheapest)
3. **OpenAI** (GPT-3.5-turbo)
4. **Ollama** (local, if running)

Set at least one API key for race analysis.

---

# Modal Deployment Guide (v2.0)

> **📅 Updated:** April 2026 | **⚠️ Note:** Project refactored to `core_agent/`. Modal deployment is deprecated in v2.0 - use Docker instead.

## 📁 File Structure (Legacy - v1.0)

```
core_agent/
├── core/deploy_modal.py        # Deployment helper (legacy)
├── core/modal_app.py          # Main Modal app (legacy)
└── core/modal_config.py       # Modal configuration (legacy)
```

> **Note:** In v2.0, we use Docker via `docker compose up -d` instead of Modal.
> 
> **New in v2.0 (June 2026):**
> - ATR data flow (Market Movers, Predictor, Results) with resilient fetching
> - 15 MAF tools including 4 new ATR/dream tools
> - Self-healing parsers with adaptive selectors
> - TTL cleanup (7 days) and staleness alerts (3-hour threshold)

---

## 🛠️ Updating

```bash
# Update code and redeploy
modal deploy modal_app.py

# Update secrets
python deploy_modal.py
```

---

## 🚨 Troubleshooting

### "Secret not found"
```bash
python deploy_modal.py  # Re-create secrets
```

### "Deployment failed"
```bash
modal app logs strike-tips  # Check logs
```

### "No AI analysis"
- Check that at least one AI API key is set
- Verify API keys are valid

---

## 📊 Monitoring

```bash
# View app status
modal app list

# View function calls
modal app history strike-tips

# View logs
modal app logs strike-tips --follow
```

---

**🏇 Deployed on Modal - Bet Smart!**
