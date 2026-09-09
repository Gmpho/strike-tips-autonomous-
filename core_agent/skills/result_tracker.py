"""
Result Tracker - Auto-settle open bets using search service (DDGS + direct SA scraper).
Uses fuzzy matching on horse names with date fallback (today → yesterday → no date).
"""

import logging
import re
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("result-tracker")


# Max age for AUTO-settlement. Older PENDING bets are left alone for manual
# review: settling a week-old bet against yesterday's results for the same
# track+race number would usually settle the WRONG race (usually as LOST).
MAX_SETTLE_AGE_DAYS = 3


def _bet_age_days(bet_date: Optional[str]) -> Optional[int]:
    """Age of a bet in days from its ISO date, or None if unparseable."""
    if not bet_date:
        return None
    try:
        return (date.today() - date.fromisoformat(str(bet_date)[:10])).days
    except (ValueError, TypeError):
        return None


def _is_exotic_bet(bet) -> bool:
    """Exotic pool tickets (PICK6:1-2-3..., confidence EXOTIC) can't be settled
    from single-winner results — they need pool dividends. Skip them here."""
    try:
        if str(getattr(bet, "confidence", "") or "").upper() == "EXOTIC":
            return True
        return ":" in str(getattr(bet, "horse", "") or "")
    except Exception:
        return False


def atr_date_label(bet_date: Optional[str]) -> str:
    """Convert a BetRecord ISO date (YYYY-MM-DD) to the relative day label the
    ATR results pages understand (today/yesterday).

    Passing the raw ISO string used to build /results/2026-09-04 URLs that 404,
    silently killing the primary settlement source for every bet.
    """
    if not bet_date:
        return "yesterday"
    try:
        d = date.fromisoformat(str(bet_date)[:10])
    except (ValueError, TypeError):
        return "yesterday"
    delta = (date.today() - d).days
    if delta <= 0:
        return "today"
    return "yesterday"


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
            atr_date = atr_date_label(bet_date)
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

    def _extract_race_winner(self, text: str) -> Optional[str]:
        """Extract the confirmed winning horse name from result text if present."""
        if not text:
            return None
        patterns = [
            r'Winner:\s*([A-Za-z0-9\'\-\s]+?)(?:\s*\(1st\)|\s+in\s+race|$|\.)',
            r'(?:^|\s)1st\s+([A-Za-z0-9\'\-\s]{3,30})(?:\s*\(|\s+odds|\s+sp|$|\.|\,)',
            r'won\s+by\s+([A-Za-z0-9\'\-\s]{3,30})(?:\s*\(|\s+odds|$|\.|\,)',
        ]
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                w = m.group(1).strip()
                if w and len(w) >= 3 and not any(kw in w.lower() for kw in ["race", "track", "south africa", "result", "winner"]):
                    return w
        return None

    async def check_and_settle_open_bets(
        self, max_age_days: int = MAX_SETTLE_AGE_DAYS
    ) -> List[Dict]:
        """
        Main entry point: check all open bets and auto-settle if result found.
        Settles BOTH winning and losing bets once race results are confirmed.
        Bets older than max_age_days are DEFERRED (left PENDING for manual
        review) — settling them against recent results would usually hit the
        wrong race. Unparseable dates fail open (settled normally).
        Returns list of settled bet records.
        """
        try:
            from core_agent.core.strike_brain import brain
        except Exception as brain_import_err:
            logger.debug(f"strike_brain unavailable, using injected governor: {brain_import_err}")
            brain = None
        gov = self.governor or (brain.strike.bankroll if brain and brain.strike else None)
        if not gov:
            return []

        open_bets = gov.get_open_bets()
        if not open_bets:
            return []

        settled = []
        deferred: List[str] = []
        for bet in open_bets:
            if _is_exotic_bet(bet):
                logger.debug(
                    "Skipping exotic ticket %s (%s) — needs pool dividends, not single-winner results",
                    bet.bet_id, bet.horse,
                )
                continue
            age = _bet_age_days(getattr(bet, "date", None))
            if age is not None and age > max_age_days:
                deferred.append(f"{bet.bet_id} ({bet.horse} @ {bet.track} R{bet.race_number}, {age}d old)")
                continue
            result_text = await self._search_result(bet.track, bet.race_number, bet_date=bet.date)
            if not result_text:
                continue

            # 1. Direct check if our horse is declared winner
            winner, confidence = self._extract_winner(result_text, [bet.horse])
            settle_needed = False
            won = False
            notes = ""

            if winner and confidence >= 0.55:
                won = True
                settle_needed = True
                notes = f"Auto-settled (WINNER confirmed, confidence={confidence:.0%})"
            else:
                # 2. Check if a DIFFERENT winner was confirmed for this race
                confirmed_winner = self._extract_race_winner(result_text)
                if confirmed_winner:
                    match_score = self._fuzzy_match(confirmed_winner, bet.horse)
                    if match_score >= 0.55:
                        won = True
                        settle_needed = True
                        notes = f"Auto-settled (WINNER: {confirmed_winner}, confidence={match_score:.0%})"
                    else:
                        won = False
                        settle_needed = True
                        notes = f"Auto-settled (LOST - 1st was {confirmed_winner})"

            if settle_needed:
                settled_ok = False
                try:
                    if brain and brain.strike:
                        # settle_bet returns a status dict (never raises on a
                        # failed settle) — honor its "settled" flag instead of
                        # assuming success, or we log/notify phantom settles.
                        _res = brain.strike.settle_bet(bet.bet_id, won=won, notes=notes)
                        settled_ok = bool(_res.get("settled")) if isinstance(_res, dict) else bool(_res)
                except Exception as brain_err:
                    logger.debug(f"Brain settle fallback to governor: {brain_err}")

                if not settled_ok and gov:
                    settled_ok = gov.settle_bet(bet.bet_id, won=won, notes=notes)

                if settled_ok:
                    logger.info(
                        f"Auto-settled: {bet.horse} at {bet.track} R{bet.race_number} - {'WON' if won else 'LOST'} ({notes})"
                    )
                    profit_loss = (bet.actual_return or 0.0) - bet.stake if won else -bet.stake
                    try:
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
                            "notes": notes,
                        }
                    )

        if deferred:
            logger.info(
                "Deferred %d stale bet(s) older than %dd for manual review: %s",
                len(deferred), max_age_days, "; ".join(deferred[:10]),
            )
        return settled
