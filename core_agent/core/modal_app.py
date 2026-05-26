"""
Strike Tips — Modal Cloud Deployment

Entry points:
  serve_api:         FastAPI ASGI app + Telegram webhook (always-on)
  run_scan:          One-shot daily scan (manual or cron)
  run_odds_monitor:  Continuous odds monitoring (runs until stopped)

Usage:
  modal deploy core_agent.core.modal_app        # deploy everything
  modal run core_agent.core.modal_app:run_scan   # one-off scan
"""

import modal
import logging

logger = logging.getLogger("modal-app")

image = modal.Image.from_dockerfile("Dockerfile")

app = modal.App("strike-tips-racing")

data_volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)

secrets = [modal.Secret.from_name("strike-tips-secrets")]


# ── ASGI: FastAPI + Telegram webhook ──────────────────────────────────
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=2048,
    timeout=3600,
)
@modal.asgi_app()
def serve_api():
    """Mount core_agent.api FastAPI app + inject /telegram-webhook route."""
    from core_agent.api import app as fastapi_app
    from fastapi import Request

    @fastapi_app.post("/telegram-webhook")
    async def telegram_webhook(request: Request):
        import os
        import telegram
        from core_agent.core.strike_brain import brain

        body = await request.json()
        msg = body.get("message", {})
        text = msg.get("text", "")
        chat_id = msg.get("chat", {}).get("id")
        if not text or not chat_id:
            return {"ok": True}

        logger.info("Telegram from %s: %.80s", chat_id, text)
        brain.initialize()
        try:
            reply = (await brain.pipeline.chat(text)).summary
            await telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"]).send_message(
                chat_id=chat_id, text=reply, parse_mode="Markdown"
            )
        except Exception as exc:
            logger.error("Webhook error: %s", exc, exc_info=True)
            try:
                await telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"]).send_message(
                    chat_id=chat_id, text=f"Error: {exc!s}"
                )
            except Exception:
                pass
        return {"ok": True}

    return fastapi_app


# ── Register Telegram Webhook ─────────────────────────────────────────
@app.function(
    image=image,
    secrets=secrets,
    timeout=30,
)
def register_webhook():
    """Register (or inspect) the Telegram bot webhook pointing at our Modal app."""
    import os
    import httpx

    token = os.environ["TELEGRAM_BOT_TOKEN"]
    url = "https://gmpho--strike-tips-racing-serve-api.modal.run/telegram-webhook"

    r = httpx.post(
        f"https://api.telegram.org/bot{token}/setWebhook",
        json={"url": url, "allowed_updates": ["message"]},
    )
    data = r.json()
    if data.get("ok"):
        logger.info("Webhook registered → %s", url)
    else:
        logger.error("Webhook failed: %s", data)

    # Confirm
    info = httpx.get(f"https://api.telegram.org/bot{token}/getWebhookInfo").json()
    print(f"Webhook info: {info}")
    return info


# ── Daily Scan (scheduled) ────────────────────────────────────────────
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=2048,
    timeout=3600,
    schedule=modal.Cron("0 5 * * *", timezone="Africa/Johannesburg"),
)
def daily_scan():
    """Scheduled daily scan — runs at 05:00 SAST every day."""
    import subprocess

    logger.info("Scheduled daily scan starting...")
    result = subprocess.run(
        ["python3", "core_agent/core/strike_tips.py", "scan"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    return {"status": "complete"}


@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=2048,
    timeout=3600,
)
def run_scan():
    """Run strike-tips daily scan for all tracks (manual one-shot)."""
    import subprocess

    logger.info("Starting Strike Tips Scan on Modal...")
    result = subprocess.run(
        ["python3", "core_agent/core/strike_tips.py", "scan"],
        capture_output=True,
        text=True,
    )
    print(result.stdout)
    if result.stderr:
        print(f"Errors: {result.stderr}")
    return {"status": "complete"}


# ── Odds Monitor (continuous) ─────────────────────────────────────────
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=1536,
    timeout=43200,
)
async def run_odds_monitor():
    """Continuous odds monitoring (12h timeout, auto-restart on crash)."""
    from core_agent.core.adaptive_odds_monitor import AdaptiveOddsMonitor

    monitor = AdaptiveOddsMonitor()
    logger.info("Odds monitor started")
    await monitor.run()
