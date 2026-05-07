"""
Learning Engine - Tracks ROI by track, distance, and odds range.
Improves probability estimates over time using historical bet results.
"""

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("learning-engine")

MIN_SAMPLES = 5  # Minimum bets before applying adjustments
MAX_ADJUSTMENT = 0.30  # Max ±30% probability adjustment


@dataclass
class SegmentStats:
    """Performance stats for a specific betting segment"""

    bets: int = 0
    wins: int = 0
    total_staked: float = 0.0
    total_returned: float = 0.0

    @property
    def win_rate(self) -> float:
        return self.wins / self.bets if self.bets > 0 else 0.0

    @property
    def roi(self) -> float:
        return (
            ((self.total_returned - self.total_staked) / self.total_staked * 100.0)
            if self.total_staked > 0
            else 0.0
        )

    @property
    def has_enough_data(self) -> bool:
        return self.bets >= MIN_SAMPLES


class LearningEngine:
    """
    Tracks betting performance by segment (track, distance, odds range)
    and learns which bets are most profitable over time.
    """

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = os.path.abspath(data_dir)
        self._file = os.path.join(self.data_dir, "learning_stats.json")
        self._stats: Dict[str, Dict] = {}
        self._load()

    def _load(self):
        if os.path.exists(self._file):
            try:
                with open(self._file) as f:
                    self._stats = json.load(f)
            except Exception:
                self._stats = {}

    def _save(self):
        try:
            with open(self._file, "w") as f:
                json.dump(self._stats, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not save learning stats: {e}")

    def _get_segment_key(self, track: str, distance: Optional[int], odds: float) -> str:
        """Build a segment key for grouping bets"""
        dist_bucket = "any"
        if distance:
            if distance <= 1200:
                dist_bucket = "sprint"
            elif distance <= 1600:
                dist_bucket = "mile"
            else:
                dist_bucket = "staying"

        odds_bucket = "short" if odds < 4.0 else ("mid" if odds < 8.0 else "long")
        return f"{track.lower()}:{dist_bucket}:{odds_bucket}"

    def record_result(
        self,
        track: str,
        distance: Optional[int],
        odds: float,
        stake: float,
        won: bool,
        actual_return: float,
    ):
        """Record a bet result to update segment statistics"""
        key = self._get_segment_key(track, distance, odds)
        if key not in self._stats:
            self._stats[key] = {
                "bets": 0,
                "wins": 0,
                "total_staked": 0.0,
                "total_returned": 0.0,
            }

        self._stats[key]["bets"] += 1
        self._stats[key]["total_staked"] += stake
        self._stats[key]["total_returned"] += actual_return
        if won:
            self._stats[key]["wins"] += 1

        self._save()

    def get_adjustment_factor(
        self, track: str, distance: Optional[int], odds: float
    ) -> float:
        """
        Return a probability adjustment factor for a segment.
        Only applied if MIN_SAMPLES bets have been recorded.
        Returns a multiplier: 1.0 = no change, 1.3 = +30%, 0.7 = -30%
        """
        key = self._get_segment_key(track, distance, odds)
        stats = self._stats.get(key)

        if not stats or stats["bets"] < MIN_SAMPLES:
            return 1.0  # Not enough data yet

        # Expected win rate at given odds
        implied_prob = 1.0 / max(odds, 1.01)
        actual_win_rate = stats["wins"] / stats["bets"]

        # Adjustment = ratio of actual to implied
        if implied_prob > 0:
            adjustment = actual_win_rate / implied_prob
        else:
            adjustment = 1.0

        # Clamp to ±30%
        return max(1.0 - MAX_ADJUSTMENT, min(1.0 + MAX_ADJUSTMENT, adjustment))

    def get_roi_by_track(self) -> Dict[str, float]:
        """Return ROI grouped by track"""
        track_stats: Dict[str, Dict] = {}
        for key, stats in self._stats.items():
            track = key.split(":")[0]
            if track not in track_stats:
                track_stats[track] = {"staked": 0.0, "returned": 0.0}
            track_stats[track]["staked"] += stats["total_staked"]
            track_stats[track]["returned"] += stats["total_returned"]

        return {
            track: (
                round((v["returned"] - v["staked"]) / v["staked"] * 100, 1)
                if v["staked"] > 0
                else 0.0
            )
            for track, v in track_stats.items()
        }
