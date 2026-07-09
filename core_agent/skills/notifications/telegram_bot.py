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


def _get_whitelist_ids() -> set[int]:
    """Load the set of authorized chat_ids from whitelist.json on disk."""
    try:
        from core_agent.core.access_control import _load_whitelist
        return _load_whitelist()
    except Exception as e:
        logger.warning("Could not load whitelist: %s", e)
        return set()


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
            logger.warning("Telegram send to %s failed: %s", chat_id, response.text)
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
            f"📝 <i>{reasoning[:200]}</i>\n\n"
            f"⚠️ Bet responsibly. Max 5% per bet rule applied."
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
        await self.broadcast(text)
        return True

    async def broadcast(self, text: str, parse_mode: str = "HTML") -> None:
        """Send to the admin + every authorized whitelisted user, chunking at 4000 chars."""
        targets: list[str] = [self.chat_id]
        for cid in _get_whitelist_ids():
            sid = str(cid)
            if sid not in targets:
                targets.append(sid)
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for t in targets:
            for chunk in chunks:
                try:
                    await self._send_to_chat(t, chunk, parse_mode)
                except Exception:
                    pass

    async def send_daily_tips(self, scan_results: Dict[str, List[Dict]]) -> bool:
        """Send a daily summary of all value bets found asynchronously"""
        total_value_bets = sum(
            len(r.get("value_bets", []))
            for races in scan_results.values()
            for r in races
        )

        lines = [f"🏇 <b>STRIKE TIPS - Daily Intelligence Report</b>\n"]
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
