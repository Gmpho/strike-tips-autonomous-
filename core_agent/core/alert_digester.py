"""
AlertDigester — batches non-critical alerts into periodic digests
to reduce Telegram spam while keeping users informed.

Architecture:
  - Non-critical alerts (odds-drop, value-bet) are pushed onto a queue.
  - The queue is mirrored to a JSONL file on the data volume so alerts
    survive container churn: Modal cron containers exit after a single
    cycle and serve containers scale to zero ~60s after the last request,
    which used to discard every queued alert (Sep-2026: "alerts stopped
    coming" — the 30-min flush loop never lived long enough to run).
  - Flush rules:
      * long-lived processes run the background loop every interval;
      * short-lived callers (the odds-monitor cron) call ``flush_due()``
        at the end of each cycle;
      * ``flush_due()`` ships only entries older than ``interval`` and
        keeps fresh ones for later cycles, so the 30-min batching intent
        (anti-spam) is preserved while delivery is guaranteed;
      * entries leave the queue only after a successful broadcast
        (retry-safe; worst case a duplicate digest, never a lost one);
      * ``flush()`` force-sends everything — for graceful shutdown.
  - Critical alerts (bet results, errors) bypass the digester entirely.

Usage:
  digester = AlertDigester(notifier)
  await digester.push("odds_drop", "🏇 <b>...")
  await digester.push_critical("bet_result", "🎉 <b>...")
  await digester.flush_due()   # short-lived callers, once per cycle
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime
from typing import Dict, List, Optional

from core_agent.skills.notifications.telegram_bot import TelegramNotifier

logger = logging.getLogger("alert-digester")

DEFAULT_INTERVAL = int(os.getenv("DIGEST_INTERVAL_SECONDS", "1800"))  # 30 min
QUEUE_FILENAME = "alert_digest_queue.jsonl"
SENT_FILENAME = "alert_digest_sent.json"
# Identical alert content is not re-sent inside this window, even across
# container churn (Sep-2026: every 5-min cron re-pushed the same 20 alerts
# with fresh timestamps and the digest re-sent them forever).
RESENT_WINDOW_SECS = 6 * 3600
MAX_DIGEST_ITEMS = 20  # per message — keeps under Telegram length limits


def _default_queue_path() -> str:
    try:
        from core_agent.config.paths import DATA_DIR

        return str(DATA_DIR / QUEUE_FILENAME)
    except Exception:
        return QUEUE_FILENAME


def _default_sent_path() -> str:
    try:
        from core_agent.config.paths import DATA_DIR

        return str(DATA_DIR / SENT_FILENAME)
    except Exception:
        return SENT_FILENAME


class AlertDigester:
    """Durable, batch-then-send alert queue (see module docstring)."""

    def __init__(
        self,
        notifier: TelegramNotifier,
        interval: int = DEFAULT_INTERVAL,
        queue_path: Optional[str] = None,
    ):
        self._notifier = notifier
        self._interval = interval
        self._queue_path = queue_path or _default_queue_path()
        self._sent_path = os.path.join(os.path.dirname(self._queue_path) or ".", SENT_FILENAME)
        self._queue: List[dict] = []  # in-process view; the file is the truth
        self._lock = asyncio.Lock()
        self._task: Optional[asyncio.Task] = None
        self._running = False
        # Cooldown counters reported by the AlertEngine; rendered into the
        # next digest as "⏱ Suppressed: N by per-race/… cooldown" and reset
        # after each actual send (not after queueing).
        self._suppressed: dict = {}

    # ── durability helpers ────────────────────────────────────────────

    @staticmethod
    def _key(rec: dict) -> tuple:
        # Content identity WITHOUT timestamp: the same alert re-detected on
        # the next cycle must dedupe against the queued copy.
        return (rec.get("category"), rec.get("html"))

    def _load_file(self) -> List[dict]:
        """Read the durable queue (tolerates missing/corrupt lines)."""
        out: List[dict] = []
        try:
            with open(self._queue_path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue
                    if isinstance(rec, dict) and rec.get("html"):
                        out.append(rec)
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.debug("Digest queue read failed: %s", e)
        return out

    def _merge(self) -> None:
        """Merge the durable file view into memory (cross-container pushes)."""
        seen = {self._key(e) for e in self._queue}
        for rec in self._load_file():
            k = self._key(rec)
            if k not in seen:
                self._queue.append(rec)
                seen.add(k)

    def _append_line(self, rec: dict) -> None:
        try:
            with open(self._queue_path, "a") as f:
                f.write(json.dumps(rec) + "\n")
        except Exception as e:
            logger.debug("Digest queue append failed: %s", e)

    def _persist(self) -> None:
        """Atomically rewrite the durable queue from memory."""
        try:
            tmp = f"{self._queue_path}.tmp"
            with open(tmp, "w") as f:
                for rec in self._queue:
                    f.write(json.dumps(rec) + "\n")
            os.replace(tmp, self._queue_path)
        except Exception as e:
            logger.debug("Digest queue persist failed: %s", e)

    def note_suppressed(self, stats: dict) -> None:
        """Record cooldown counters for the next digest (see ``_send_digest``).

        Accumulated (not replaced): several monitor cycles pass between
        flushes, and every cycle's suppressions must be visible, not just
        the last cycle's.
        """
        if not stats:
            return
        self._suppressed = {
            "race_cooldown_prevents": int(self._suppressed.get("race_cooldown_prevents", 0) or 0)
            + int(stats.get("race_cooldown_prevents", 0) or 0),
            "cooldown_prevents": int(self._suppressed.get("cooldown_prevents", 0) or 0)
            + int(stats.get("cooldown_prevents", 0) or 0),
        }

    def _load_sent(self) -> Dict[str, float]:
        """{repr(key): sent_epoch} pruned to the resend window. Survives
        container churn via the data volume (in-memory cooldowns don't)."""
        try:
            with open(self._sent_path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return {}
            cutoff = time.time() - RESENT_WINDOW_SECS
            return {k: float(v) for k, v in data.items() if float(v) > cutoff}
        except Exception:
            return {}

    def _record_sent(self, keys) -> None:
        try:
            sent = self._load_sent()
            now = time.time()
            for k in keys:
                sent[repr(k)] = now
            tmp = f"{self._sent_path}.tmp"
            with open(tmp, "w") as f:
                json.dump(sent, f)
            os.replace(tmp, self._sent_path)
        except Exception as e:
            logger.debug("Digest sent-registry persist failed: %s", e)

    async def push(self, category: str, html: str) -> None:
        """Queue a non-critical alert for the next digest (durable).

        Skips content already delivered inside the resend window — each
        monitor cycle re-detects the same odds drops with fresh timestamps,
        and without this the same digest re-sends forever (Sep-2026).
        """
        await self._ensure_loop()
        rec = {"ts": time.time(), "category": category, "html": html}
        key = self._key(rec)
        try:
            if repr(key) in self._load_sent():
                logger.debug("Digest push skipped (sent recently): %s", html[:60])
                return
        except Exception:
            pass
        async with self._lock:
            self._queue.append(rec)
            self._append_line(rec)

    async def push_critical(self, category: str, html: str) -> None:
        """Send a critical alert immediately, bypassing the digest queue."""
        await self._ensure_loop()
        text = f"🚨 <b>{category.replace('_', ' ').title()}</b>\n\n{html}"
        await self._notifier.broadcast(text)

    async def _send_digest(self, items: List[dict]) -> List[dict]:
        """Send items in chunks; return only the records that were delivered."""
        sent: List[dict] = []
        for i in range(0, len(items), MAX_DIGEST_ITEMS):
            chunk = items[i : i + MAX_DIGEST_ITEMS]
            lines = [
                f"📋 <b>Alert Digest</b> — {datetime.now().strftime('%H:%M')}",
                f"({len(chunk)} alert(s) in the last {self._interval // 60} min)\n",
            ]
            for rec in chunk:
                icon = {"odds_drop": "📉", "value_bet": "💰"}.get(
                    rec.get("category", ""), "ℹ️"
                )
                lines.append(f"{icon} {rec.get('html', '')}")

            # What the cooldowns suppressed since the last *sent* digest —
            # a thin digest is explainable instead of looking like lost alerts.
            suppressed: List[str] = []
            race_cd = int(self._suppressed.get("race_cooldown_prevents", 0) or 0)
            horse_cd = int(self._suppressed.get("cooldown_prevents", 0) or 0)
            if race_cd:
                suppressed.append(f"{race_cd} by per-race cooldown")
            if horse_cd:
                suppressed.append(f"{horse_cd} by per-horse cooldown")
            if suppressed:
                lines.append(f"\n⏱ Suppressed: {', '.join(suppressed)}")

            lines.append("\n⚡ Critical alerts are sent immediately — not batched.")
            try:
                ok = await self._notifier.broadcast("\n".join(lines))
            except Exception as e:
                logger.warning("Digest send raised (will retry next flush): %s", e)
                break  # keep this chunk + the rest for the next flush
            if ok is False:
                logger.warning("Digest send failed (will retry next flush)")
                break
            self._suppressed = {}
            sent.extend(chunk)
        return sent

    async def flush_due(self, force: bool = False) -> int:
        """Send queued alerts older than the interval; keep the rest.

        Returns the number of entries shipped. Fresh entries stay queued
        (and on disk) for later cycles — this is how the digest cadence
        survives short-lived containers.
        """
        async with self._lock:
            self._merge()
            cutoff = time.time() - self._interval
            due: List[dict] = []
            for rec in self._queue:
                try:
                    if force or float(rec.get("ts") or 0) <= cutoff:
                        due.append(rec)
                except Exception:
                    due.append(rec)
        if not due:
            return 0

        sent = await self._send_digest(due)
        if sent:
            sent_keys = {self._key(r) for r in sent}
            self._record_sent(sent_keys)
            async with self._lock:
                # Re-merge so pushes that landed during the send survive.
                self._merge()
                self._queue = [r for r in self._queue if self._key(r) not in sent_keys]
                self._persist()
        return len(sent)

    async def flush(self) -> None:
        """Force-send everything queued (graceful shutdown path)."""
        try:
            await self.flush_due(force=True)
        except Exception as e:
            logger.warning("Digest flush error: %s", e)

    async def _loop(self) -> None:
        """Background loop that flushes on interval (long-lived processes)."""
        while self._running:
            await asyncio.sleep(self._interval)
            try:
                await self.flush_due()
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
            self._merge()
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
