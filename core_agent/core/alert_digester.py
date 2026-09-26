"""
AlertDigester — batches non-critical alerts into periodic digests
to reduce Telegram spam while keeping users informed.

Architecture:
  - Non-critical alerts (odds-drop, value-bet) are pushed onto a queue.
  - A background flush task runs every DIGEST_INTERVAL seconds.
  - On flush, all queued alerts are formatted into one message and sent.
  - Critical alerts (bet results, errors) bypass the digester entirely.

Usage:
  digester = AlertDigester(notifier)
  await digester.push("odds_drop", "🏇 <b>...")
  await digester.push_critical("bet_result", "🎉 <b>...")
  # start/stop for background loop
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from core_agent.skills.notifications.telegram_bot import TelegramNotifier

logger = logging.getLogger("alert-digester")

DEFAULT_INTERVAL = int(os.getenv("DIGEST_INTERVAL_SECONDS", "1800"))  # 30 min


class AlertDigester:
    """Buffers non-critical alerts and flushes them on a timer."""

    def __init__(self, notifier: TelegramNotifier, interval: int = DEFAULT_INTERVAL):
        self._notifier = notifier
        self._interval = interval
        self._queue: list[tuple[str, str]] = []  # (category, formatted_html)
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def push(self, category: str, html: str) -> None:
        """Queue a non-critical alert for the next digest."""
        await self._ensure_loop()
        async with self._lock:
            self._queue.append((category, html))

    async def push_critical(self, category: str, html: str) -> None:
        """Send a critical alert immediately, bypassing the digest queue."""
        await self._ensure_loop()
        text = f"🚨 <b>{category.replace('_', ' ').title()}</b>\n\n{html}"
        await self._notifier.broadcast(text)

    async def flush(self) -> None:
        """Send all queued alerts as one digest message, then clear."""
        async with self._lock:
            if not self._queue:
                return
            batch = self._queue[:]
            self._queue.clear()

        if not batch:
            return

        lines = [
            f"📋 <b>Alert Digest</b> — {datetime.now().strftime('%H:%M')}",
            f"({len(batch)} alert(s) in the last {self._interval // 60} min)\n",
        ]

        for category, html in batch[-20:]:  # cap at 20 to avoid message length limits
            icon = {"odds_drop": "📉", "value_bet": "💰"}.get(category, "ℹ️")
            lines.append(f"{icon} {html}")

        lines.append("\n⚡ Critical alerts are sent immediately — not batched.")

        await self._notifier.broadcast("\n".join(lines))

    async def _loop(self) -> None:
        """Background loop that flushes on interval."""
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                await self.flush()
            except Exception as e:
                logger.warning("Digest flush error: %s", e)

    def start(self) -> None:
        """Mark the digester as running. Safe from sync code — creates no task.

        Call start_async() once an event loop is available to start the
        background flush loop.  push() and push_critical() also attempt
        to start it lazily on first use.
        """
        if self._running:
            return
        self._running = True
        logger.info("AlertDigester marked running (interval=%ss)", self._interval)

    async def start_async(self) -> None:
        """Start the background loop from async context. Idempotent."""
        if self._running and self._task is None:
            self._task = asyncio.create_task(self._loop())
            logger.info("AlertDigester background loop started")

    async def _ensure_loop(self) -> None:
        """Lazily start the background loop if needed."""
        if self._running and self._task is None:
            try:
                self._task = asyncio.create_task(self._loop())
                logger.info("AlertDigester background loop started (lazy)")
            except RuntimeError:
                pass

    async def stop(self) -> None:
        """Stop the background loop and flush remaining alerts."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self.flush()
        logger.info("AlertDigester stopped")
