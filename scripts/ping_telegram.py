"""One-shot Telegram delivery proof (user-requested, Sep-2026).

Sends a single clearly-labelled test message via the production notifier
(admin + whitelist). Run: modal run scripts/ping_telegram.py::ping
"""

import modal

app = modal.App("telegram-ping-test")
image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("python-dotenv", "httpx")
    .add_local_file(
        "core_agent/skills/notifications/telegram_bot.py",
        "/app/core_agent/skills/notifications/telegram_bot.py",
    )
)
secrets = [modal.Secret.from_name("strike-tips-secrets")]


@app.function(image=image, secrets=secrets, timeout=120)
async def ping() -> dict:
    import sys

    sys.path.insert(0, "/app")
    from core_agent.skills.notifications.telegram_bot import TelegramNotifier

    notifier = TelegramNotifier()
    ok = await notifier.broadcast(
        "🔔 <b>Strike Tips delivery test</b>\n"
        "Requested from the HUD terminal — if you read this, the Telegram "
        "pipe (bot token → admin chat) is open end-to-end."
    )
    return {"delivered": ok}
