"""
Learning Engine - Tracks ROI by track, distance, and odds range.
Improves probability estimates over time using historical bet results.
"""

import json
import logging
import os
import math
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

    def refresh_from_ledger(self, force: bool = False) -> bool:
        """Rebuild real segment stats from bet_history.json.

        The auto-settler (result_tracker) never called record_result, so this
        file froze in mid-Oct while the ledger kept settling (incl. exotics).
        Rebuilding from the ledger fixes history, not just future bets, and
        needs no settlement-code changes. Dream priors are preserved; only
        real bet counts are recomputed. Throttled by ledger mtime.
        """
        ledger = os.path.join(self.data_dir, "bet_history.json")
        try:
            ledger_mtime = os.path.getmtime(ledger)
        except OSError:
            return False

        if not force and getattr(self, "_ledger_mtime", None) == ledger_mtime:
            return False
        self._ledger_mtime = ledger_mtime

        try:
            with open(ledger) as f:
                rows = json.load(f)
        except Exception as e:
            logger.warning(f"[LEARN] Ledger refresh skipped: {e}")
            return False
        if not isinstance(rows, list):
            return False

        # Keep dream-only segments (and their priors) intact.
        rebuilt: Dict[str, Dict] = {
            key: {"dream_bets": stats.get("dream_bets", 0), "dream_wins": stats.get("dream_wins", 0)}
            for key, stats in self._stats.items()
            if stats.get("dream_bets")
        }

        recorded = 0
        for bet in rows:
            if str(bet.get("status") or "").upper() not in ("WON", "LOST"):
                continue
            track = str(bet.get("track") or "").strip().lower()
            if len(track) < 4:
                continue
            try:
                odds = float(bet.get("odds") or 0.0)
                stake = float(bet.get("stake") or 0.0)
            except (TypeError, ValueError):
                continue
            if odds <= 0 or stake <= 0:
                continue
            distance = bet.get("distance")
            try:
                distance = int(distance) if distance else None
            except (TypeError, ValueError):
                distance = None

            key = self._get_segment_key(track, distance, odds)
            stats = rebuilt.setdefault(
                key, {"bets": 0, "wins": 0, "total_staked": 0.0, "total_returned": 0.0}
            )
            stats.setdefault("bets", 0)
            stats.setdefault("wins", 0)
            stats.setdefault("total_staked", 0.0)
            stats.setdefault("total_returned", 0.0)
            stats["bets"] += 1
            stats["total_staked"] += stake
            stats["total_returned"] += float(
                bet.get("payout") if bet.get("payout") is not None else bet.get("actual_return") or 0.0
            )
            if str(bet.get("status") or "").upper() == "WON":
                stats["wins"] += 1
            recorded += 1

        self._stats = rebuilt
        self._save()
        logger.info(f"[LEARN] Rebuilt segment stats from ledger: {recorded} settled bets")
        return True

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

    def record_dream_result(
        self,
        track: str,
        distance: Optional[int],
        odds: float,
        won: bool,
    ):
        """Record a simulated/dreamed bet result to bootstrap segment statistics"""
        key = self._get_segment_key(track, distance, odds)
        if key not in self._stats:
            self._stats[key] = {
                "bets": 0,
                "wins": 0,
                "total_staked": 0.0,
                "total_returned": 0.0,
                "dream_bets": 0,
                "dream_wins": 0,
            }

        stats = self._stats[key]
        stats["dream_bets"] = stats.get("dream_bets", 0) + 1
        if won:
            stats["dream_wins"] = stats.get("dream_wins", 0) + 1

        self._save()
        logger.info(
            f"[LEARN] Recorded dream result for {key}: "
            f"wins={stats['dream_wins']}/{stats['dream_bets']}"
        )

    def record_result(
        self,
        track: str,
        distance: Optional[int],
        odds: float,
        stake: float,
        won: bool,
        actual_return: float,
    ):
        """Record a real bet result to update segment statistics"""
        key = self._get_segment_key(track, distance, odds)
        if key not in self._stats:
            self._stats[key] = {
                "bets": 0,
                "wins": 0,
                "total_staked": 0.0,
                "total_returned": 0.0,
                "dream_bets": 0,
                "dream_wins": 0,
            }

        stats = self._stats[key]
        stats["bets"] += 1
        stats["total_staked"] += stake
        stats["total_returned"] += actual_return
        if won:
            stats["wins"] += 1

        self._save()

    def get_adjustment_factor(
        self, track: str, distance: Optional[int], odds: float
    ) -> float:
        """
        Return a probability adjustment factor for a segment.
        Uses Bayesian Beta-Binomial updates where simulated dreams act as 
        priors that decay as real settled bets accumulate (Option A).
        """
        key = self._get_segment_key(track, distance, odds)
        stats = self._stats.get(key)

        if not stats:
            return 1.0

        real_bets = stats.get("bets", 0)
        real_wins = stats.get("wins", 0)
        dream_bets = stats.get("dream_bets", 0)
        dream_wins = stats.get("dream_wins", 0)

        # Apply exponential decay to dream priors as real bets accumulate (k=0.15)
        decay = math.exp(-0.15 * real_bets)
        effective_dream_bets = dream_bets * decay

        # Total sample weight check: needs at least MIN_SAMPLES total weight
        if (real_bets + effective_dream_bets) < MIN_SAMPLES:
            return 1.0

        # Prior distribution parameters (from decayed simulated outcomes)
        alpha_prior = 1.0 + (dream_wins * decay)
        beta_prior = 1.0 + ((dream_bets - dream_wins) * decay)

        # Posterior distribution parameters (Prior + Likelihood)
        alpha_post = alpha_prior + real_wins
        beta_post = beta_prior + (real_bets - real_wins)

        # Expected win rate from posterior
        p_bayesian = alpha_post / (alpha_post + beta_post)

        # Implied win rate at given odds
        p_implied = 1.0 / max(odds, 1.01)

        # Adjustment ratio
        adjustment = p_bayesian / p_implied if p_implied > 0 else 1.0

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
            track: round((v["returned"] - v["staked"]) / v["staked"] * 100, 1)
            for track, v in track_stats.items()
            if v["staked"] > 0
        }
