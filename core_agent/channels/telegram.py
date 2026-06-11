from __future__ import annotations
import asyncio
import logging
import os

from core_agent.bus.events import InboundMessage, OutboundMessage
from core_agent.bus.queue import MessageBus

logger = logging.getLogger("telegram-channel")

POLL_INTERVAL = 1.0


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
                if out.done and not out.content:
                    continue
                try:
                    await self._bot.send_message(
                        chat_id=out.chat_id,
                        text=out.content,
                        parse_mode=out.parse_mode or "Markdown",
                    )
                except Exception as e:
                    logger.warning("Telegram send error to %s: %s", out.chat_id, e)
        except asyncio.CancelledError:
            pass
        finally:
            self.bus.unsubscribe(sub)
