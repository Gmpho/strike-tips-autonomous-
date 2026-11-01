from __future__ import annotations
import asyncio
import logging
import os

from core_agent.bus.events import InboundMessage, OutboundMessage
from core_agent.bus.queue import MessageBus
from core_agent.config.settings import COMPLIANCE

logger = logging.getLogger("telegram-channel")

POLL_INTERVAL = 1.0
PAPER_MODE_PREFIX = "[PAPER MODE] " if COMPLIANCE.paper_trading else ""


class TelegramChannel:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self._bot = None
        self._offset = 0
        self._poll_task: asyncio.Task | None = None
        self._send_task: asyncio.Task | None = None
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
                try:
                    prefixed_content = f"{PAPER_MODE_PREFIX}{out.content}"
                    try:
                        await self._bot.send_message(
                            chat_id=out.chat_id,
                            text=prefixed_content,
                            parse_mode=out.parse_mode or "Markdown",
                        )
                    except Exception as parse_err:
                        # Unbalanced Markdown entities crash Telegram's parser;
                        # retry once as plain text so the message isn't lost.
                        if "parse" in str(parse_err).lower():
                            await self._bot.send_message(
                                chat_id=out.chat_id,
                                text=prefixed_content,
                            )
                        else:
                            raise
                except Exception as e:
                    logger.warning("Telegram send error to %s: %s", out.chat_id, e)
        except asyncio.CancelledError:
            pass
        finally:
            self.bus.unsubscribe(sub)
