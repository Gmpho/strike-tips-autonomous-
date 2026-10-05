"""
Telegram Notifications Skill
Sends value bet alerts, bet confirmations, results, and daily summaries
via Telegram Bot API.

All public send_* methods broadcast to the admin (TELEGRAM_CHAT_ID) AND
every authorized user in the whitelist (users who authenticated via PIN).
Call `send_message(text, admin_only=True)` for sensitive messages (errors).
"""

import logging
import os
import httpx
import asyncio
from typing import Dict, List, Optional

logger = logging.getLogger("telegram-notifier")

# Chats that blocked the bot (Telegram 403). Kept on the data volume so one
# dead recipient can never fail a whole broadcast again (Sep-2026: a single
# blocked subscriber kept every digest in "retry forever" and the user saw
# the same 20 alerts every cycle).
QUARANTINE_FILENAME = "telegram_blocked.json"
# Backstop TTL (Oct-2026): a quarantine is a spam guard, not a life sentence.
# Proof-of-life (any inbound message / successful link) clears immediately;
# anything older than this expires on read.
QUARANTINE_TTL_SECS = 7 * 24 * 3600


def _quarantine_path() -> Optional[str]:
    try:
        from core_agent.config.paths import DATA_DIR

        return str(DATA_DIR / QUARANTINE_FILENAME)
    except Exception:
        return None


def _quarantined_ids() -> set:
    path = _quarantine_path()
    if not path:
        return set()
    try:
        import json
        import time

        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return set()
        now = time.time()
        live = set()
        expired = []
        for k, v in data.items():
            ts = float((v or {}).get("ts", 0)) if isinstance(v, dict) else 0
            if ts and now - ts > QUARANTINE_TTL_SECS:
                expired.append(k)
            else:
                live.add(str(k))
        if expired:
            try:
                for k in expired:
                    data.pop(k, None)
                with open(f"{path}.tmp", "w") as f:
                    json.dump(data, f)
                os.replace(f"{path}.tmp", path)
            except Exception:
                pass
            logger.info("Telegram quarantine TTL-expired chats released: %s", expired)
        return live
    except Exception:
        return set()


def _quarantine_chat(chat_id: str, reason: str) -> None:
    path = _quarantine_path()
    if not path:
        return
    try:
        import json
        import time

        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                data = {}
        except Exception:
            data = {}
        data[str(chat_id)] = {"reason": reason, "ts": time.time()}
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        logger.warning(
            "Telegram chat %s quarantined (%s) — skipped in future broadcasts", chat_id, reason
        )
        try:
            from core_agent.core.telemetry import emit
            emit("system", f"🔇 Telegram chat quarantined ({reason}) — broadcasts paused for it")
        except Exception:
            pass
    except Exception as e:
        logger.debug("Quarantine persist failed: %s", e)


def clear_quarantine(chat_id: str | int) -> bool:
    """Remove a chat from quarantine. Returns True if it was listed.

    Call on proof-of-life: any inbound message or successful passcode link
    proves the chat receives, so broadcasts must resume. Also emits
    telemetry so the release is visible, not silent.
    """
    path = _quarantine_path()
    if not path:
        return False
    try:
        import json

        try:
            with open(path) as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return False
        except Exception:
            return False
        key = str(chat_id)
        if key not in data:
            return False
        reason = (data.get(key) or {}).get("reason", "?") if isinstance(data.get(key), dict) else "?"
        data.pop(key, None)
        tmp = f"{path}.tmp"
        with open(tmp, "w") as f:
            json.dump(data, f)
        os.replace(tmp, path)
        logger.warning("Telegram chat %s released from quarantine (was: %s)", key, reason)
        try:
            from core_agent.core.telemetry import emit
            emit("system", f"🔓 Telegram chat released from quarantine (was: {reason})")
        except Exception:
            pass
        return True
    except Exception as e:
        logger.debug("Quarantine release failed: %s", e)
        return False


def _get_whitelist_ids() -> set[int]:
    """Load the set of authorized chat_ids from whitelist.json on disk."""
    try:
        from core_agent.core.access_control import _load_whitelist
        return _load_whitelist()
    except Exception as e:
        logger.warning("Could not load whitelist: %s", e)
        return set()


def _clip_reasoning(text: str, limit: int = 200) -> str:
    """Clip reasoning to a sentence boundary (never mid-sentence).

    Cuts at the last sentence end within the limit, appending an ellipsis.
    Falls back to a hard cut when no boundary exists.
    """
    t = str(text or "").strip()
    if len(t) <= limit:
        return t
    cut = max(t.rfind(". ", 0, limit), t.rfind("! ", 0, limit), t.rfind("? ", 0, limit))
    if cut > 40:
        return t[: cut + 1].strip() + " …"
    return t[:limit].rstrip() + " …"


class TelegramNotifier:
    """
    Asynchronous Telegram Bot interface for Strike Tips notifications.
    Requires TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID env vars.
    """

    BASE_URL = "https://api.telegram.org/bot{token}"

    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")

        if not self.token or not self.chat_id:
            raise ValueError(
                "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in .env"
            )

        self._base = self.BASE_URL.format(token=self.token)
        self._client: Optional[httpx.AsyncClient] = None
        self._client_loop_id: Optional[int] = None
        logger.info("TelegramNotifier initialized (admin=%s)", self.chat_id)

    async def _get_client(self) -> httpx.AsyncClient:
        current_loop = asyncio.get_running_loop()
        if (
            self._client is None
            or self._client.is_closed
            or id(current_loop) != self._client_loop_id
        ):
            if self._client is not None and not self._client.is_closed:
                await self._client.aclose()
            # Pre-resolve api.telegram.org to avoid ~33% DNS failures in Docker
            try:
                from core_agent.core.http_client import _resolve_host
                _resolve_host("api.telegram.org")
            except Exception:
                pass
            self._client = httpx.AsyncClient(timeout=10.0)
            self._client_loop_id = id(current_loop)
        return self._client

    async def _send_to_chat(self, chat_id: str, text: str, parse_mode: str = "HTML") -> bool:
        """Send a message to a single chat ID."""
        try:
            client = await self._get_client()
            response = await client.post(
                f"{self._base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
            )
            if response.status_code == 200:
                return True
            body = response.text or ""
            if response.status_code == 403 and "blocked" in body.lower():
                _quarantine_chat(str(chat_id), "blocked by user")
            else:
                logger.warning("Telegram send to %s failed: %s", chat_id, body[:200])
            return False
        except Exception as e:
            logger.error("Telegram error for %s: %s", chat_id, e)
            return False

    async def send_message(self, text: str, parse_mode: str = "HTML", admin_only: bool = False) -> bool:
        """Send a message.

        If *admin_only* is True, only the admin receives it (for errors, stack traces).
        Otherwise, it broadcasts to all authorized users.
        """
        if admin_only:
            return await self._send_to_chat(self.chat_id, text, parse_mode)
        await self.broadcast(text, parse_mode)
        return True

    async def send_photo(self, photo_bytes: bytes, caption: Optional[str] = None, parse_mode: str = "HTML", admin_only: bool = False) -> bool:
        """Send a photo."""
        if admin_only:
            return await self._send_photo_to_chat(self.chat_id, photo_bytes, caption, parse_mode)
        targets: list[str] = [self.chat_id]
        for cid in _get_whitelist_ids():
            sid = str(cid)
            if sid not in targets:
                targets.append(sid)
        for t in targets:
            try:
                await self._send_photo_to_chat(t, photo_bytes, caption, parse_mode)
            except Exception:
                pass
        return True

    async def _send_photo_to_chat(self, chat_id: str, photo_bytes: bytes, caption: Optional[str] = None, parse_mode: str = "HTML") -> bool:
        try:
            client = await self._get_client()
            files = {"photo": ("chart.png", photo_bytes, "image/png")}
            data = {"chat_id": chat_id, "parse_mode": parse_mode}
            if caption:
                data["caption"] = caption
            response = await client.post(
                f"{self._base}/sendPhoto",
                data=data,
                files=files,
            )
            return response.status_code == 200
        except Exception as e:
            logger.error("Telegram photo error for %s: %s", chat_id, e)
            return False

    async def send_value_bet(
        self,
        horse: str,
        track: str,
        race_number: int,
        race_time: str,
        odds: float,
        edge_percent: float,
        stake: float,
        confidence: str,
        reasoning: str,
        ref: str = "",
    ) -> bool:
        """Send a value bet alert asynchronously"""
        confidence_emoji = {
            "STRONG_VALUE": "🔥",
            "VALUE": "✅",
            "MARGINAL": "💛",
        }.get(confidence, "📊")

        text = (
            f"{confidence_emoji} <b>STRIKE TIPS - {confidence.replace('_', ' ')}</b>\n\n"
            f"📍 <b>{track.title()} - Race {race_number}</b> ({race_time})\n"
            f"🐎 <b>{horse}</b>\n"
            f"💰 Odds: {odds} | Edge: +{edge_percent:.1f}%\n"
            f"💵 Advised Stake: R{stake:.2f}\n\n"
            f"📝 <i>{_clip_reasoning(reasoning)}</i>\n\n"
            f"⚠️ Bet responsibly. Sized by Kelly × DSI (odds-capped)."
            + (f"\n<code>{ref}</code>" if ref else "")
        )
        await self.broadcast(text)
        return True

    async def send_bet_result(
        self,
        horse: str,
        track: str,
        race_number: int,
        won: bool,
        stake: float,
        returns: float,
        profit_loss: float,
        ref: str = "",
    ) -> bool:
        """Send a bet result notification asynchronously"""
        emoji = "🎉" if won else "❌"
        status = "WON" if won else "LOST"
        pl_str = (
            f"+R{profit_loss:.2f}" if profit_loss >= 0 else f"-R{abs(profit_loss):.2f}"
        )

        text = (
            f"{emoji} <b>Race Result - {status}</b>\n\n"
            f"🐎 {horse} | {track.title()} R{race_number}\n"
            f"💵 Stake: R{stake:.2f} | Returns: R{returns:.2f}\n"
            f"📊 P&L: <b>{pl_str}</b>"
        )
        if ref:
            text += f"\n<code>{ref}</code>"
        await self.broadcast(text)
        return True

    async def broadcast(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send to the admin + every authorized whitelisted user, chunking at 4000 chars.

        Returns True only when every chunk reached every target. Digest
        retry logic depends on this signal (Sep-2026: swallowed failures
        marked alerts as delivered while nothing arrived).
        """
        targets: list[str] = [self.chat_id]
        for cid in _get_whitelist_ids():
            sid = str(cid)
            if sid not in targets:
                targets.append(sid)
        quarantined = _quarantined_ids()
        if quarantined:
            skipped = [t for t in targets if t in quarantined]
            if skipped:
                logger.info("Broadcast skipping quarantined chats: %s", skipped)
            targets = [t for t in targets if t not in quarantined]
        try:
            from core_agent.agent.telegram_format import _split_grapheme_safe

            chunks = _split_grapheme_safe(text, 4000)
        except Exception:
            chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        ok = True
        for t in targets:
            for chunk in chunks:
                try:
                    if not await self._send_to_chat(t, chunk, parse_mode):
                        ok = False
                except Exception as e:
                    ok = False
                    logger.warning("Telegram broadcast to %s failed: %s", t, e)
        return ok

    async def send_daily_tips(self, scan_results: Dict[str, List[Dict]], title: str = "Daily Intelligence Report") -> bool:
        """Send a daily summary of all value bets found asynchronously"""
        total_value_bets = sum(
            len(r.get("value_bets", []))
            for races in scan_results.values()
            for r in races
        )

        lines = [f"🏇 <b>STRIKE TIPS - {title}</b>\n"]
        lines.append(f"📊 Found <b>{total_value_bets}</b> value bet(s)\n")

        for track, races in scan_results.items():
            vb_count = sum(len(r.get("value_bets", [])) for r in races)
            if vb_count > 0:
                lines.append(f"\n📍 <b>{track.title()}</b> — {vb_count} selections")
                for race in races:
                    insight = race.get("ai_insight", "")
                    if insight:
                        lines.append(f"  R{race['race_number']}: 💡 {insight[:150]}")
                    for vb in race.get("value_bets", [])[:2]:
                        horse_name = (
                            vb.get("horse")
                            or vb.get("name")
                            or vb.get("horse_name")
                            or "Unknown"
                        )
                        try:
                            edge = float(vb.get("edge_percent") or vb.get("edge") or 0)
                        except (ValueError, TypeError):
                            edge = 0.0
                        lines.append(
                            f"  R{race['race_number']}: {horse_name} @ {vb.get('odds_decimal', '?')} "
                            f"(+{edge:.1f}%)"
                        )

        lines.append("\n⚠️ Always bet responsibly.")
        await self.broadcast("\n".join(lines))
        return True

    async def send_exotic_plays(self, exotic_plays: List[Dict]) -> bool:
        """Send exotic pool play alerts"""
        lines = ["🎰 <b>Exotic Pool Plays Found</b>\n"]
        for play in exotic_plays:
            pool = play.get("pool", "UNKNOWN")
            legs = play.get("legs", [])
            combos = play.get("combinations", [])
            est_div = play.get("estimated_dividend", "?")
            lines.append(
                f"  🏆 <b>{pool}</b> — {len(legs)} legs, {len(combos)} combo(s)"
            )
            if legs:
                lines.append(f"    Legs: {', '.join(legs[:3])}")
            if est_div:
                lines.append(f"    Est. Dividend: R{est_div}")
        await self.broadcast("\n".join(lines))
        return True

    async def send_error_notification(self, error: str, context: str = "") -> bool:
        """Send a system error alert (admin-only, no broadcast)."""
        text = f"🚨 <b>Strike Tips Error</b>\n\n"
        if context:
            text += f"Context: {context}\n"
        text += f"Error: <code>{error[:300]}</code>"
        return await self.send_message(text, admin_only=True)

    async def close(self):
        """Cleanup the async client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
