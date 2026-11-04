from __future__ import annotations
import asyncio
import logging
import os

from core_agent.bus.events import InboundMessage, OutboundMessage
from core_agent.bus.queue import MessageBus
from core_agent.config.settings import COMPLIANCE

logger = logging.getLogger("telegram-channel")

POLL_INTERVAL = 1.0
# Telegram clears a typing indicator after ~5s, so a 20-40s model reply
# would look stalled without a keep-alive. Both transports must emit this
# every ~4s until the answer is dispatched (telegram-hud-ux spec).
TYPING_INTERVAL_SECS = 4.0
PAPER_MODE_PREFIX = "[PAPER MODE] " if COMPLIANCE.paper_trading else ""


async def telegram_typing_loop(bot, chat_id, interval_secs: float = TYPING_INTERVAL_SECS):
    """Keep Telegram's typing indicator alive until cancelled.

    Cancelling the task stops the loop cleanly (the webhook path in
    modal_app.telegram_webhook does the same around the model call).
    """
    try:
        while True:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            await asyncio.sleep(interval_secs)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # network hiccup — stop typing, never break the reply
        logger.debug("Typing loop stopped for %s: %s", chat_id, e)


class TelegramChannel:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._bot = None
        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._send_task: asyncio.Task | None = None
        self._typing_tasks: dict[str, asyncio.Task] = {}
        self._enabled = bool(self.token)

    async def start(self) -> None:
        if not self._enabled:
            logger.info("Telegram channel disabled (TELEGRAM_BOT_TOKEN not set)")
            return

        mode = os.getenv("TELEGRAM_MODE", "polling")
        if mode == "webhook":
            logger.info("Telegram channel: TELEGRAM_MODE=webhook, skipping polling (webhook handles inbound directly)")
            return

        try:
            import telegram
            self._bot = telegram.Bot(token=self.token)
            me = await self._bot.get_me()
            logger.info("Telegram channel started — bot @%s", me.username)
        except Exception as e:
            logger.warning("Telegram channel init failed: %s", e)
            self._enabled = False
            return

        self._poll_task = asyncio.create_task(self._poll_loop())
        self._send_task = asyncio.create_task(self._send_loop())

    async def stop(self) -> None:
        if self._poll_task:
            self._poll_task.cancel()
        if self._send_task:
            self._send_task.cancel()
        for task in list(self._typing_tasks.values()):
            task.cancel()
        self._typing_tasks.clear()

    def _start_typing(self, chat_id: str) -> None:
        """Begin (or keep) the typing keep-alive for this chat."""
        key = str(chat_id)
        existing = self._typing_tasks.get(key)
        if existing and not existing.done():
            return
        self._typing_tasks[key] = asyncio.create_task(
            telegram_typing_loop(self._bot, chat_id)
        )

    def _stop_typing(self, chat_id: str) -> None:
        task = self._typing_tasks.pop(str(chat_id), None)
        if task and not task.done():
            task.cancel()

    async def _poll_loop(self) -> None:
        import telegram

        while True:
            try:
                updates = await self._bot.get_updates(
                    offset=self._offset,
                    timeout=10,
                    allowed_updates=["message"],
                )
                for update in updates:
                    if update.message and update.message.text:
                        chat_id = str(update.message.chat.id)
                        text = update.message.text
                        # Proof-of-life: inbound traffic releases broadcast
                        # quarantine (Oct-2026) — talking chats get alerts.
                        try:
                            from core_agent.skills.notifications.telegram_bot import clear_quarantine
                            clear_quarantine(chat_id)
                        except Exception:
                            pass
                        # Typing must keep re-arming for the whole model
                        # call — one action dies after ~5s (telegram-hud-ux).
                        self._start_typing(chat_id)
                        msg = InboundMessage(
                            session_key=f"tg:{chat_id}",
                            channel="telegram",
                            chat_id=chat_id,
                            content=text,
                            user_id=update.message.from_user.id if update.message.from_user else None,
                        )
                        await self.bus.publish(msg)
                        logger.debug("Telegram <- %s: %s", chat_id, text[:60])
                    self._offset = update.update_id + 1
            except asyncio.CancelledError:
                break
            except telegram.error.TimedOut:
                pass
            except Exception as e:
                logger.warning("Telegram poll error: %s", e)
                await asyncio.sleep(5)
            else:
                await asyncio.sleep(POLL_INTERVAL)

    async def _send_loop(self) -> None:
        from core_agent.agent.telegram_format import (
            format_race_card_for_telegram,
            markdown_table_to_pre,
            split_for_telegram,
        )
        sub = self.bus.subscribe()
        try:
            while True:
                out: OutboundMessage = await sub.get()
                if out.channel != "telegram":
                    continue
                # Streaming deltas are for WS/REST clients; Telegram has no
                # streaming UX, so send only the final complete message.
                if out.delta and not out.done:
                    continue
                if out.done and not out.content:
                    continue
                # The answer is going out — stop re-arming the typing dot.
                self._stop_typing(out.chat_id)
                try:
                    prefixed_content = f"{PAPER_MODE_PREFIX}{out.content}"
                    # Markdown → Telegram-safe HTML, then chunk at paragraph
                    # boundaries: raw sends dropped race-card tables and
                    # >4096-char replies failed outright (Sep-2026 restore).
                    formatted_content = format_race_card_for_telegram(
                        markdown_table_to_pre(prefixed_content)
                    )
                    chunks = split_for_telegram(formatted_content, max_length=3800)
                    for chunk in chunks:
                        try:
                            await self._bot.send_message(
                                chat_id=out.chat_id,
                                text=chunk,
                                parse_mode="HTML",
                            )
                        except Exception as parse_err:
                            if "parse" in str(parse_err).lower() or "entit" in str(parse_err).lower():
                                await self._bot.send_message(
                                    chat_id=out.chat_id,
                                    text=prefixed_content[:4000],
                                )
                            else:
                                raise
                except Exception as e:
                    logger.warning("Telegram send error to %s: %s", out.chat_id, e)
        except asyncio.CancelledError:
            pass
        finally:
            self.bus.unsubscribe(sub)
