"""
Adaptive Analyzer - Applies Learning Engine adjustments to probability estimates.
"""

import logging
from typing import Dict, Optional
from .engine import LearningEngine

logger = logging.getLogger("adaptive-analyzer")


class AdaptiveAnalyzer:
    """
    Wraps the base form-based probability estimates with
    learning-driven adjustments from historical bet results.
    Adjustments are capped at ±30% and require MIN_SAMPLES bets.
    """

    def __init__(self, data_dir: str = "./data"):
        self.engine = LearningEngine(data_dir=data_dir)

    def adjust_probabilities(
        self,
        probability_estimates: Dict[str, float],
        track: str,
        distance: Optional[int] = None,
        odds_map: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Apply segment-based adjustment factors to probability estimates.

        Args:
            probability_estimates: {horse_name: base_probability}
            track: Track name for segment lookup
            distance: Race distance in metres
            odds_map: {horse_name: decimal_odds} for segment key resolution

        Returns:
            Adjusted probability dict (same keys, adjusted values)
        """
        adjusted = {}
        for horse, prob in probability_estimates.items():
            odds = (odds_map or {}).get(horse, 5.0)
            factor = self.engine.get_adjustment_factor(track, distance, odds)
            new_prob = min(max(prob * factor, 0.01), 0.99)
            adjusted[horse] = round(new_prob, 4)

            if factor != 1.0:
                logger.debug(
                    f"[LEARN] {horse} @ {track}: prob adjusted "
                    f"{prob:.2%} → {new_prob:.2%} (factor={factor:.2f})"
                )

        # Re-normalize to ensure sum ≤ 1.0 (approximate market)
        total = sum(adjusted.values())
        if total > 1.0:
            adjusted = {k: round(v / total, 4) for k, v in adjusted.items()}

        return adjusted

    def record_result(
        self,
        track: str,
        distance: Optional[int],
        odds: float,
        stake: float,
        won: bool,
        actual_return: float,
    ):
        """Proxy to learning engine - record a settled bet result"""
        self.engine.record_result(track, distance, odds, stake, won, actual_return)

    def analyze_recent_results(self) -> Dict:
        """Analyze recent betting results, compute segment ROI, and return summary.

        Called daily by scheduler.update_learning_job() to keep
        probability adjustments current.
        """
        stats = {}
        # Load raw stats from engine for summary
        try:
            if hasattr(self.engine, '_stats'):
                stats = self.engine._stats
        except Exception:
            pass

        total_bets = sum(s.get("bets", 0) for s in stats.values())
        total_wins = sum(s.get("wins", 0) for s in stats.values())
        segments_with_data = sum(1 for s in stats.values() if s.get("bets", 0) >= 5)

        print(
            f"[LEARN] Analyzed {total_bets} bets, {total_wins} wins "
            f"across {len(stats)} segments ({segments_with_data} with enough data)"
        )
        return {
            "total_bets": total_bets,
            "total_wins": total_wins,
            "segments": len(stats),
            "segments_with_data": segments_with_data,
            "roi_by_track": self.engine.get_roi_by_track(),
        }

    def get_roi_summary(self) -> Dict[str, float]:
        """Return ROI by track from the learning engine"""
        return self.engine.get_roi_by_track()
