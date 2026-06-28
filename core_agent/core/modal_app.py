"""
Strike Tips — Modal Cloud Deployment

Entry points:
  serve_api:         FastAPI ASGI app + Telegram webhook (always-on)
  run_scan:          One-shot daily scan (manual or cron)
  run_odds_monitor:  Continuous odds monitoring (runs until stopped)

Usage:
  modal run core_agent.core.modal_app:run_scan   # one-off scan
"""

import modal
import logging

logger = logging.getLogger("modal-app")

image = modal.Image.from_dockerfile("Dockerfile")

app = modal.App("strike-tips-racing")

data_volume = modal.Volume.from_name("strike-tips-data", create_if_missing=True)

secrets = [modal.Secret.from_name("strike-tips-secrets"), modal.Secret.from_name("strike-tips-api-key")]


# ── ASGI: FastAPI + Telegram webhook ──────────────────────────────────
@app.function(
    image=image,
    secrets=secrets,
    volumes={"/app/data": data_volume},
    memory=512,
    timeout=3600,
    env={"OLLAMA_HOST": "https://gmpho--strike-tips-ollama-cloud-ollama.modal.run"},
    scaledown_window=120,
    startup_timeout=120,
    min_containers=0,
)
@modal.concurrent(max_inputs=10)
@modal.asgi_app()
def serve_api():
    """Mount core_agent.api_pkg FastAPI app + inject /telegram-webhook route."""
    from core_agent.api_pkg import app as fastapi_app
    from fastapi import Request

    @fastapi_app.post("/telegram-webhook")
    async def telegram_webhook(request: Request):
        import asyncio
        import os
        import re
        import telegram
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        from core_agent.core.strike_brain import brain

        body = await request.json()
        msg = body.get("message", {})
        text = (msg.get("text", "") or "").strip()
        chat_id = msg.get("chat", {}).get("id")
        if not text or not chat_id:
            return {"ok": True}

        logger.info("Telegram from %s: %.80s", chat_id, text)
        brain.initialize()
        bot = telegram.Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])

        # ── Access control ───────────────────────────────────────────
        from core_agent.config.settings import NOTIFICATIONS
        from core_agent.core.access_control import is_authorized, authorize

        owner_id = NOTIFICATIONS.telegram_chat_id
        pin = NOTIFICATIONS.access_pin

        if not is_authorized(chat_id, owner_id):
            try:
                if text.startswith("/auth"):
                    parts = text.split()
                    if len(parts) == 2 and parts[1] == pin:
                        authorize(chat_id)
                        await bot.send_message(
                            chat_id=chat_id,
                            text="✅ *Access granted!* You can now use the bot.",
                            parse_mode="Markdown",
                        )
                    else:
                        await bot.send_message(
                            chat_id=chat_id,
                            text="🔒 *Invalid PIN.* Access denied.",
                            parse_mode="Markdown",
                        )
                else:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=(
                            "🔒 *Restricted Access*\n\n"
                            "This bot requires authorization. "
                            f"Send `/auth <PIN>` to gain access."
                        ),
                        parse_mode="Markdown",
                    )
            except telegram.error.BadRequest:
                logger.warning("Cannot reach chat_id %s (may not exist)", chat_id)
            return {"ok": True}

        _TAG_REPLACEMENTS = {
            "[RACE]": "🏇", "[LOC]": "📍", "[DATE]": "📅", "[STATS]": "📊",
            "[OK]": "✅", "[ERR]": "❌", "[WARN]": "⚠️", "[LOOKUP]": "🔍",
            "[BOT]": "🤖", "[CHAT]": "💬", "[START]": "🚀", "[SCAN]": "🔄",
            "[HIT]": "🎯", "[TIME]": "⏰", "[MAF]": "🧠", "[STOP]": "🛑",
            "[WORLD]": "🌍", "[SA]": "🇿🇦", "[UK]": "🇬🇧", "[AU]": "🇦🇺",
            "[US]": "🇺🇸", "[IE]": "🇮🇪", "[FR]": "🇫🇷", "[HK]": "🇭🇰",
            "[JP]": "🇯🇵", "[SAVE]": "💾", "[HEALTH]": "🏥", "[SEC]": "🔐",
            "[SIGNAL]": "📡", "[NO]": "🚫", "[IDEA]": "💡", "[PKG]": "📦",
            "[VASE]": "🏺", "[MSG]": "📨", "[FAST]": "⚡", "[RUN]": "🏃",
            "[LIST]": "📋", "[HI]": "👋", "[LINK]": "🔗", "[NOTE]": "📝",
            "[Y]": "✓", "[X]": "✗", "[INFO]": "ℹ️",
            "Status: online": "✅ Online",
        }

        def _clean(text: str) -> str:
            for tag, emoji in _TAG_REPLACEMENTS.items():
                text = text.replace(tag, emoji)
            return re.sub(r"\[([A-Z]{2,})\]", "", text).strip()

        try:
            # ── Command dispatch ────────────────────────────────────
            if text.startswith("/"):
                parts = text.split()
                cmd = parts[0].lower()

                if cmd == "/auth":
                    return {"ok": True}

                if cmd == "/start":
                    from core_agent.config.settings import NOTIFICATIONS
                    welcome = (
                        "🏇 *Strike Tips Agent*\n\n"
                        "I'm your AI Racing Data Analyst. Just chat with me or use commands:\n\n"
                        "/auth <PIN> - Unlock bot access\n"
                        "/scan - Daily race scan\n"
                        "/status - Quick balance check\n"
                        "/chart - Performance chart\n"
                        "/help - Show all commands"
                    )
                    kb = [[InlineKeyboardButton("🚀 Open Intelligence HUD", web_app={"url": NOTIFICATIONS.twa_url})]]
                    await bot.send_message(chat_id=chat_id, text=welcome, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
                    return {"ok": True}

                if cmd == "/help":
                    from core_agent.config.settings import NOTIFICATIONS
                    help_text = (
                        "🧠 *Available Commands*\n\n"
                        "/auth <PIN> - Unlock bot access\n"
                        "/scan - Start today's full racing scan\n"
                        "/status - Get current bankroll & ROI stats\n"
                        "/chart - Show 15-day performance chart\n"
                        "/clear - Reset conversation history\n\n"
                        "*Ask me things like:*\n"
                        '• "Who is the top value pick at Vaal?"\n'
                        '• "Show me my open bets"\n'
                        '• "Calculate edge for horse A at 6.0 odds"'
                    )
                    kb = [[InlineKeyboardButton("🚀 Open Intelligence HUD", web_app={"url": NOTIFICATIONS.twa_url})]]
                    await bot.send_message(chat_id=chat_id, text=help_text, reply_markup=InlineKeyboardMarkup(kb), parse_mode="Markdown")
                    return {"ok": True}

                if cmd == "/status":
                    if not brain.strike:
                        await bot.send_message(chat_id=chat_id, text="❌ System not initialized")
                        return {"ok": True}
                    s = brain.strike.get_bankroll_status()
                    reply = (
                        f"💰 *Account Summary*\n\n"
                        f"Balance: *R{s['current_bankroll']:.2f}*\n"
                        f"P&L: *R{s['total_profit_loss']:.2f}*\n"
                        f"Open Bets: *{s['open_bets']}*\n"
                        f"Drawdown: *{s['drawdown_percent']:.1f}%*"
                    )
                    await bot.send_message(chat_id=chat_id, text=reply, parse_mode="Markdown")
                    return {"ok": True}

                if cmd == "/chart":
                    if not brain.strike:
                        await bot.send_message(chat_id=chat_id, text="❌ System not initialized")
                        return {"ok": True}
                    await bot.send_message(chat_id=chat_id, text="📊 *Generating Performance Chart...*", parse_mode="Markdown")
                    from core_agent.tools.visualizer import PerformanceVisualizer
                    history = brain.strike.bankroll.get_history_stats(days=15)
                    if not history:
                        await bot.send_message(chat_id=chat_id, text="⚠️ No betting history found yet.")
                        return {"ok": True}
                    chart_bytes = await PerformanceVisualizer.generate_bankroll_chart(history)
                    if chart_bytes:
                        await bot.send_photo(chat_id=chat_id, photo=chart_bytes, caption="📈 *Strike Tips — 15 Day Performance*", parse_mode="Markdown")
                    else:
                        await bot.send_message(chat_id=chat_id, text="❌ Failed to render chart.")
                    return {"ok": True}

                if cmd == "/scan":
                    if not brain.strike:
                        await bot.send_message(chat_id=chat_id, text="❌ System not initialized")
                        return {"ok": True}
                    await bot.send_message(chat_id=chat_id, text="🔄 *Starting Daily Scan...*\n_This may take 30-60 seconds._", parse_mode="Markdown")
                    try:
                        result = await brain.strike.run_daily_scan()
                        reply = (
                            f"✅ *Daily Scan Complete*\n\n"
                            f"Tracks: *{result.get('tracks_scanned', 0)}*\n"
                            f"Value Bets: *{result.get('total_value_bets', 0)}*\n"
                            f"Auto-Bets: *{result.get('auto_bets_placed', 0)}*"
                        )
                    except Exception as e:
                        reply = f"❌ *Scan Failed*\n`{str(e)[:200]}`"
                    await bot.send_message(chat_id=chat_id, text=reply, parse_mode="Markdown")
                    return {"ok": True}

                if cmd == "/clear":
                    await bot.send_message(chat_id=chat_id, text="🧹 *Conversation history cleared.*", parse_mode="Markdown")
                    return {"ok": True}

            # ── AI pipeline (non-command): bus-based chat ─────────
            from core_agent.bus.events import InboundMessage, OutboundMessage

            inbound = InboundMessage(
                session_key=f"tg:{chat_id}",
                channel="telegram",
                chat_id=str(chat_id),
                content=text,
                user_id=msg.get("from", {}).get("id"),
            )
            bus = request.app.state.bus
            sub = bus.subscribe()
            await bus.publish(inbound)

            reply = ""
            try:
                while True:
                    out = await asyncio.wait_for(sub.get(), timeout=180.0)
                    if out.channel == "telegram" and str(out.chat_id) == str(chat_id):
                        if out.done:
                            reply = out.content or ""
                            break
            except asyncio.TimeoutError:
                reply = "⏳ I'm still thinking. Please try a simpler question or check back later."
            finally:
                bus.unsubscribe(sub)

            reply = _clean(reply)
            MAX_LENGTH = 4000
            if len(reply) > MAX_LENGTH:
                for i in range(0, len(reply), MAX_LENGTH):
                    await bot.send_message(chat_id=chat_id, text=reply[i:i+MAX_LENGTH], parse_mode="Markdown")
            else:
                await bot.send_message(chat_id=chat_id, text=reply, parse_mode="Markdown")

        except Exception as exc:
            logger.error("Webhook error: %s", exc, exc_info=True)
            try:
                await bot.send_message(chat_id=chat_id, text=f"Error: {exc!s}")
            except Exception:
                pass
        return {"ok": True}

    # ── Auto-register webhook on boot ────────────────────────────────
    import os
    import httpx
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    webhook_url = "https://gmpho--strike-tips-racing-serve-api.modal.run/telegram-webhook"
    try:
        r = httpx.post(
            f"https://api.telegram.org/bot{token}/setWebhook",
            json={"url": webhook_url, "allowed_updates": ["message"]},
            timeout=10,
        )
        if r.json().get("ok"):
            logger.info("Telegram webhook auto-registered → %s", webhook_url)
        else:
            logger.error("Webhook auto-registration failed: %s", r.json())
    except Exception as exc:
        logger.error("Webhook auto-registration error: %s", exc)

    return fastapi_app


# ── Register Telegram Webhook (manual) ────────────────────────────────
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


# ── Odds Monitor (now runs via Docker, pushes to Cloudflare KV) ─────────
@app.function(
    image=image,
    secrets=[modal.Secret.from_name("cloudflare-mcp")] + secrets,
    volumes={"/app/data": data_volume},
    memory=512,
    timeout=43200,
    min_containers=0,
    container_idle_timeout=120,
    env={"OLLAMA_HOST": "https://gmpho--strike-tips-ollama-cloud-ollama.modal.run"}
)
async def run_odds_monitor():
    """Continuous odds monitoring (fallback — Docker handles now)."""
    from core_agent.core.adaptive_odds_monitor import AdaptiveOddsMonitor

    monitor = AdaptiveOddsMonitor()
    logger.info("Odds monitor started")
    await monitor.run()
