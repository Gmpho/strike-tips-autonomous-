"""
Telegram Notifications Skill
Sends value bet alerts, bet confirmations, results, and daily summaries
via Telegram Bot API.
"""

import logging
import os
import requests
from typing import Dict, List, Optional

logger = logging.getLogger("telegram-notifier")


class TelegramNotifier:
    """
    Telegram Bot interface for Strike Tips notifications.
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
        logger.info("TelegramNotifier initialized")

    def send_message(self, text: str, parse_mode: str = "HTML") -> bool:
        """Send a raw message to the configured chat"""
        try:
            response = requests.post(
                f"{self._base}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    "text": text,
                    "parse_mode": parse_mode,
                },
                timeout=10,
            )
            if response.status_code == 200:
                return True
            logger.warning(f"Telegram send failed: {response.text}")
            return False
        except Exception as e:
            logger.error(f"Telegram error: {e}")
            return False

    def send_value_bet(
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
        """Send a value bet alert"""
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
        return self.send_message(text)

    def send_bet_result(
        self,
        horse: str,
        track: str,
        race_number: int,
        won: bool,
        stake: float,
        returns: float,
        profit_loss: float,
    ) -> bool:
        """Send a bet result notification"""
        emoji = "🎉" if won else "❌"
        status = "WON" if won else "LOST"
        pl_str = f"+R{profit_loss:.2f}" if profit_loss >= 0 else f"-R{abs(profit_loss):.2f}"

        text = (
            f"{emoji} <b>Race Result - {status}</b>\n\n"
            f"🐎 {horse} | {track.title()} R{race_number}\n"
            f"💵 Stake: R{stake:.2f} | Returns: R{returns:.2f}\n"
            f"📊 P&L: <b>{pl_str}</b>"
        )
        return self.send_message(text)

    def send_daily_tips(self, scan_results: Dict[str, List[Dict]]) -> bool:
        """Send a daily summary of all value bets found"""
        total_value_bets = sum(
            len(r.get("value_bets", [])) for races in scan_results.values() for r in races
        )

        lines = [f"🏇 <b>STRIKE TIPS - Daily Intelligence Report</b>\n"]
        lines.append(f"📊 Found <b>{total_value_bets}</b> value bet(s)\n")

        for track, races in scan_results.items():
            vb_count = sum(len(r.get("value_bets", [])) for r in races)
            if vb_count > 0:
                lines.append(f"\n📍 <b>{track.title()}</b> — {vb_count} selections")
                for race in races:
                    for vb in race.get("value_bets", [])[:2]:
                        lines.append(
                            f"  R{race['race_number']}: {vb['horse']} @ {vb['odds_decimal']} "
                            f"(+{vb['edge_percent']}%)"
                        )

        lines.append("\n⚠️ Always bet responsibly.")
        return self.send_message("\n".join(lines))

    def send_error_notification(self, error: str, context: str = "") -> bool:
        """Send a system error alert"""
        text = f"🚨 <b>Strike Tips Error</b>\n\n"
        if context:
            text += f"Context: {context}\n"
        text += f"Error: <code>{error[:300]}</code>"
        return self.send_message(text)

    def close(self):
        """Cleanup (no persistent connection needed for requests)"""
        pass
