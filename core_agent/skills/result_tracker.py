"""
Result Tracker - Auto-settle open bets using search service (DDGS + direct SA scraper).
Uses fuzzy matching on horse names with date fallback (today → yesterday → no date).
"""

import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("result-tracker")


def _iter_dates() -> List[str]:
    """Return date strings to try: today, yesterday, day-before, then bare."""
    today = date.today()
    return [
        today.strftime("%d %B %Y"),
        (today - timedelta(days=1)).strftime("%d %B %Y"),
        (today - timedelta(days=2)).strftime("%d %B %Y"),
    ]


class ResultTracker:
    """
    Automatically settles open bets by searching for race results
    via unified SearchService + direct SA scraper.
    """

    def __init__(self, bankroll_governor=None):
        self.governor = bankroll_governor

    def _fuzzy_match(self, name_a: str, name_b: str) -> float:
        a = set(name_a.lower().split())
        b = set(name_b.lower().split())
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        return intersection / max(len(a), len(b))

    async def _search_result(self, track: str, race_number: int, bet_date: Optional[str] = None) -> Optional[str]:
        """Search for race result text — tries ATR first, then DDGS + direct SA sites."""
        # Primary: ATR structured results (most reliable for SA racing)
        try:
            from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI
            atr = AtTheRacesAPI()
            atr_date = bet_date or "yesterday"
            winner = await atr.get_winner_for_bet(track, race_number, date=atr_date)
            if winner:
                logger.info(
                    "[RESULT] ATR winner: %s at %s R%s (odds %s)",
                    winner["horse"], track, race_number, winner.get("odds", "?"),
                )
                return f"Winner: {winner['horse']} (1st) in race {race_number} at {track}"
        except Exception as e:
            logger.debug(f"ATR lookup failed for {track} R{race_number}: {e}")

        # Fallback: DDGS with each date, then bare
        from core_agent.skills.search_service import search_racing
        for dt_str in _iter_dates():
            query = f"{track} Race {race_number} result winner {dt_str} South Africa horse racing"
            try:
                result = await search_racing(query, limit=5)
                snippets = [r.get("snippet", "") for r in result.get("results", [])]
                text = " ".join(snippets)
                if text and len(text) > 60:
                    return text
            except Exception as e:
                logger.debug(f"DDGS attempt failed ({dt_str}): {e}")

        # Bare query — no date
        try:
            query = f"{track} Race {race_number} result winner South Africa horse racing"
            result = await search_racing(query, limit=5)
            snippets = [r.get("snippet", "") for r in result.get("results", [])]
            text = " ".join(snippets)
            if text and len(text) > 60:
                return text
        except Exception as e:
            logger.debug(f"DDGS bare attempt failed: {e}")

        return await self._scrape_sa_results_direct(track, race_number)

    async def _scrape_sa_results_direct(
        self, track: str, race_number: int
    ) -> Optional[str]:
        """Direct scrape of known SA racing results pages as last resort."""
        from core_agent.core.http_client import get_async_client

        track_code_map = {
            "vaal": "XVA",
            "turffontein": "XTD",
            "fairview": "XFA",
            "scottsville": "XED",
            "kenilworth": "XCP",
            "durbanville": "XDU",
            "greyville": "XGR",
        }

        yesterday = (date.today() - timedelta(days=1)).isoformat()
        code = track_code_map.get(track.lower())
        if not code:
            return None

        urls = [
            f"https://www.tab4racing.com/results/{yesterday}",
            f"https://www.tab.co.za/tabs/horse/all/{yesterday}/{code}",
            f"https://www.racingvitesse.co.za/results?track={code}&date={yesterday}",
            "https://raceform.co.za/cards-results",
        ]

        client = get_async_client(timeout=8)
        for url in urls:
            try:
                r = await client.get(url, headers={"Accept": "text/html"})
                if r.status_code == 200 and len(r.text) > 200:
                    cleaned = self._clean_html(r.text)
                    logger.info(
                        f"[RESULT] Direct SA fetch OK: {url} ({len(cleaned)} chars)"
                    )
                    if cleaned:
                        return cleaned
            except Exception as e:
                logger.debug(f"Direct fetch failed {url}: {e}")

        return None

    @staticmethod
    def _clean_html(html: str) -> str:
        html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL)
        html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL)
        html = re.sub(r"<[^>]+>", " ", html)
        html = re.sub(r"&[a-z]+;", " ", html)
        html = re.sub(r"\s+", " ", html).strip()
        lines = [l.strip() for l in html.split("\n") if len(l.strip()) > 30]
        return "\n".join(lines)[:3000]

    def _extract_winner(
        self, text: str, candidates: List[str]
    ) -> Tuple[Optional[str], float]:
        """
        Try to find one of the candidate horse names as the WINNER in result text.
        Returns (horse_name, confidence_score).
        Uses position indicators to avoid marking non-winners as wins.
        """
        if not text:
            return None, 0.0

        text_lower = text.lower()

        for candidate in candidates:
            cl = candidate.lower()
            patterns = [
                rf'(?:^|\s)1st\s+[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)1\.\s*[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)winner:?\s*[^.?!]*?\b{re.escape(cl)}\b',
                rf'(?:^|\s)won\s+by\s+[^.?!]*?\b{re.escape(cl)}\b',
                rf'\b{re.escape(cl)}\b.*?\b1st\b',
            ]
            for pat in patterns:
                if re.search(pat, text_lower):
                    return candidate, 1.0

        return None, 0.0

    async def check_and_settle_open_bets(self) -> List[Dict]:
        """
        Main entry point: check all open bets and auto-settle if result found.
        Returns list of settled bet records.
        """
        if not self.governor:
            return []

        open_bets = self.governor.get_open_bets()
        if not open_bets:
            return []

        settled = []
        for bet in open_bets:
            result_text = await self._search_result(bet.track, bet.race_number, bet_date=bet.date)
            if not result_text:
                continue

            winner, confidence = self._extract_winner(result_text, [bet.horse])
            if winner and confidence >= 0.55:
                won = True
                success = self.governor.settle_bet(
                    bet.bet_id,
                    won=won,
                    notes=f"Auto-settled (confidence={confidence:.0%})",
                )
                if success:
                    logger.info(
                        f"Auto-settled: {bet.horse} at {bet.track} R{bet.race_number} - {'WON' if won else 'LOST'}"
                    )
                    profit_loss = (bet.actual_return or 0.0) - bet.stake
                    try:
                        from core_agent.core.strike_brain import brain
                        if brain and brain.strike and brain.strike.telegram:
                            await brain.strike.telegram.send_bet_result(
                                horse=bet.horse,
                                track=bet.track,
                                race_number=bet.race_number,
                                won=won,
                                stake=bet.stake,
                                returns=bet.actual_return or 0.0,
                                profit_loss=profit_loss,
                            )
                    except Exception as tg_err:
                        logger.warning(f"Failed to dispatch Telegram result alert: {tg_err}")

                    settled.append(
                        {
                            "bet_id": bet.bet_id,
                            "horse": bet.horse,
                            "track": bet.track,
                            "race_number": bet.race_number,
                            "won": won,
                            "confidence": confidence,
                        }
                    )

        return settled
