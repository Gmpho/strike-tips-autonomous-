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
        # Suppression accounting (from AlertEngine.stats) so a thin digest can
        # explain itself instead of looking like alerts went missing.
        self._suppressed: dict = {}
        self._last_flush_ts: Optional[datetime] = None

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

        # Honest window: buffers flush per monitor cycle (~5 min on Modal),
        # so the header must not claim "last 30 min".
        now = datetime.now()
        if self._last_flush_ts is not None:
            elapsed_min = max(1, int((now - self._last_flush_ts).total_seconds() // 60))
        else:
            elapsed_min = self._interval // 60
        self._last_flush_ts = now

        lines = [
            f"📋 <b>Alert Digest</b> — {now.strftime('%H:%M')}",
            f"({len(batch)} alert(s) in the last {elapsed_min} min)\n",
        ]

        for category, html in batch[-20:]:  # cap at 20 to avoid message length limits
            icon = {"odds_drop": "📉", "value_bet": "💰"}.get(category, "ℹ️")
            lines.append(f"{icon} {html}")

        suppressed = []
        if self._suppressed:
            race_cd = int(self._suppressed.get("race_cooldown_prevents", 0) or 0)
            key_cd = int(self._suppressed.get("cooldown_prevents", 0) or 0)
            if race_cd:
                suppressed.append(f"{race_cd} by per-race cooldown")
            if key_cd:
                suppressed.append(f"{key_cd} by per-horse cooldown")
            self._suppressed = {}
        if suppressed:
            lines.append(f"\n⏱ Suppressed: {', '.join(suppressed)}")

        lines.append("\n⚡ Critical alerts are sent immediately — not batched.")

        await self._notifier.broadcast("\n".join(lines))

    def note_suppressed(self, stats: dict) -> None:
        """Record AlertEngine cooldown counters for the next digest header."""
        if not stats:
            return
        self._suppressed = {
            "race_cooldown_prevents": stats.get("race_cooldown_prevents", 0),
            "cooldown_prevents": stats.get("cooldown_prevents", 0),
        }

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
