"""
Result Tracker - Auto-settle open bets using search service (Brave → Tavily → DDGS).
Uses fuzzy matching on horse names to handle slight name variations.
"""

import logging
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("result-tracker")


class ResultTracker:
    """
    Automatically settles open bets by searching for race results
    via unified SearchService. Uses fuzzy matching to handle horse name variations.
    Runs on a schedule (every 5 minutes post-race).
    """

    def __init__(self, bankroll_governor=None):
        self.governor = bankroll_governor

    def _fuzzy_match(self, name_a: str, name_b: str) -> float:
        """Simple character-overlap ratio for horse name matching"""
        a = set(name_a.lower().split())
        b = set(name_b.lower().split())
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        return intersection / max(len(a), len(b))

    async def _search_result(self, track: str, race_number: int) -> Optional[str]:
        """Search for race result text via unified SearchService."""
        try:
            from core_agent.skills.search_service import search_racing
            today = date.today().strftime("%d %B %Y")
            query = f"{track} Race {race_number} result winner {today} South Africa horse racing"
            result = await search_racing(query, limit=5)
            snippets = [r.get("snippet", "") for r in result.get("results", [])]
            return " ".join(snippets) if snippets else None
        except Exception as e:
            logger.warning(f"Search failed for {track} R{race_number}: {e}")
            return None

    def _extract_winner(
        self, text: str, candidates: List[str]
    ) -> Tuple[Optional[str], float]:
        """
        Try to find one of the candidate horse names in the result text.
        Returns (horse_name, confidence_score).
        """
        if not text:
            return None, 0.0

        text_lower = text.lower()
        best_match = None
        best_score = 0.0

        for candidate in candidates:
            # Direct substring match
            if candidate.lower() in text_lower:
                return candidate, 1.0

            # Fuzzy word match
            words = candidate.lower().split()
            found_words = sum(1 for w in words if w in text_lower)
            score = found_words / len(words) if words else 0.0

            if score > best_score:
                best_score = score
                best_match = candidate

        return (best_match, best_score) if best_score >= 0.6 else (None, 0.0)

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
            result_text = self._search_result(bet.track, bet.race_number)
            if not result_text:
                continue

            winner, confidence = self._extract_winner(result_text, [bet.horse])
            if winner and confidence >= 0.6:
                won = winner == bet.horse
                success = self.governor.settle_bet(
                    bet.bet_id,
                    won=won,
                    notes=f"Auto-settled (confidence={confidence:.0%})",
                )
                if success:
                    logger.info(
                        f"Auto-settled: {bet.horse} at {bet.track} R{bet.race_number} - {'WON' if won else 'LOST'}"
                    )
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
