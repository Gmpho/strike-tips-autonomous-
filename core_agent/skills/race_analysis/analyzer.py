"""
Race Analysis Skill - Core Value Bet Engine
Identifies value bets using probability edge analysis and Kelly Criterion staking.
"""

import logging
import polars as pl
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

logger = logging.getLogger("race-analysis")


@dataclass
class Runner:
    """Represents a horse in a race"""

    horse_name: str
    odds_decimal: float
    odds_fractional: Optional[str] = None
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    barrier: Optional[int] = None
    weight: Optional[float] = None
    last_5_runs: Optional[List[int]] = None  # e.g. [1, 2, 3, 1, 4]
    age: Optional[int] = None
    sex: Optional[str] = None
    # Betfair enrichment (optional, for AI context)
    gear: Optional[str] = None
    days_since_run: Optional[int] = None
    runner_comments: Optional[str] = None
    jockey_claim: Optional[str] = None
    official_rating: Optional[int] = None
    pedigree: Optional[str] = None
    owner: Optional[str] = None
    verdict: Optional[str] = None


@dataclass
class RaceCard:
    """Full race card for a single race"""

    track: str
    race_number: int
    race_time: str
    distance: Optional[int] = None  # metres; None when the source gives none — never a placeholder
    track_condition: str = "Good"  # Good, Soft, Heavy, etc.
    runners: List[Runner] = field(default_factory=list)
    race_class: Optional[str] = None
    prize_money: Optional[float] = None
    # The meeting date of the card this race belongs to (ISO). None = the
    # source did not say (treated as today). TAB/Computaform publish the
    # NEXT meeting early, so "today" is not a safe assumption.
    meeting_date: Optional[str] = None


@dataclass
class ValueBet:
    """A value bet opportunity identified by analysis"""

    horse: str
    track: str
    race_number: int
    race_time: str
    odds_decimal: float
    estimated_probability: float
    implied_probability: float
    edge_percent: float
    kelly_stake_percent: float
    advised_stake: float
    confidence: str  # STRONG_VALUE, VALUE, MARGINAL
    reasoning: str


class RaceAnalyzer:
    """
    Core value bet engine.
    Identifies value bets using probability edge analysis (estimated vs implied).
    Applies Half-Kelly criterion for stake sizing, capped at 5% of bankroll.
    """

    MIN_EDGE_PERCENT: float = 5.0
    KELLY_FRACTION: float = 0.5
    MAX_BET_PERCENT: float = 5.0

    def __init__(self, bankroll: float = 1000.0):
        self.bankroll = bankroll

    def calculate_implied_probability(self, decimal_odds: float) -> float:
        """Convert decimal odds to implied probability"""
        if decimal_odds <= 1.0:
            return 1.0
        return 1.0 / decimal_odds

    def calculate_edge(self, estimated_prob: float, decimal_odds: float) -> float:
        """Calculate the edge as a percentage"""
        implied_prob = self.calculate_implied_probability(decimal_odds)
        return (estimated_prob - implied_prob) * 100.0

    def calculate_kelly_stake(
        self, estimated_prob: float, decimal_odds: float
    ) -> float:
        """
        Calculate Half-Kelly stake as a percentage of bankroll.
        Full Kelly = (bp - q) / b  where b=odds-1, p=est_prob, q=1-est_prob
        We use Half-Kelly (0.5x) for safety.
        """
        b = decimal_odds - 1.0
        p = estimated_prob
        q = 1.0 - p

        if b <= 0 or p <= 0:
            return 0.0

        full_kelly = (b * p - q) / b
        half_kelly = full_kelly * self.KELLY_FRACTION

        # Cap at max bet percent
        return min(max(half_kelly * 100.0, 0.0), self.MAX_BET_PERCENT)

    def get_confidence(self, edge_percent: float) -> str:
        """Classify confidence level based on edge"""
        if edge_percent >= 15.0:
            return "STRONG_VALUE"
        elif edge_percent >= 8.0:
            return "VALUE"
        elif edge_percent >= self.MIN_EDGE_PERCENT:
            return "MARGINAL"
        else:
            return "NO_VALUE"

    def analyze_race(
        self,
        race_card: RaceCard,
        probability_estimates: Dict[str, float],
        reasoning_map: Optional[Dict[str, str]] = None,
    ) -> List[ValueBet]:
        """
        Analyze a full race card using Polars for vectorized performance.
        """
        runners_data = []
        skipped = 0
        for runner in race_card.runners:
            if runner.horse_name not in probability_estimates:
                continue
            # A runner with no price cannot be valued. The old 5.0 sentinel
            # invented a 20% implied chance for every unpriced runner, so a
            # PDF card with no odds produced a whole field of identical "5.0
            # +7.0%" value bets (Nov-2026 Turffontein report, 17 selections).
            # Skip instead: callers hydrate live odds before asking.
            try:
                safe_odds = float(runner.odds_decimal)
            except (ValueError, TypeError):
                safe_odds = 0.0
            if safe_odds <= 1.0:
                skipped += 1
                continue

            runners_data.append(
                {
                    "name": runner.horse_name,
                    "odds": safe_odds,
                    "est_prob": probability_estimates[runner.horse_name],
                }
            )

        if skipped:
            logger.warning(
                "analyze_race: %d/%d runners had no usable odds and were skipped "
                "(never priced at a fabricated 5.0)",
                skipped,
                len(race_card.runners),
            )

        if not runners_data:
            return []

        df = pl.DataFrame(runners_data)

        # Vectorized calculations
        df = df.with_columns(
            [
                (pl.col("est_prob") - (1.0 / pl.col("odds")))
                .mul(100.0)
                .alias("edge_percent"),
                (
                    (
                        (pl.col("odds") - 1.0) * pl.col("est_prob")
                        - (1.0 - pl.col("est_prob"))
                    )
                    / (pl.col("odds") - 1.0)
                ).alias("kelly"),
            ]
        )

        # Kelly Calculation
        df = df.with_columns(
            [
                (pl.col("kelly") * self.KELLY_FRACTION * 100.0).alias(
                    "kelly_stake_percent"
                )
            ]
        )

        # Filter for value and clamp stake
        df = df.filter(pl.col("edge_percent") >= self.MIN_EDGE_PERCENT)
        df = df.with_columns(
            [
                pl.col("kelly_stake_percent")
                .clip(0.0, self.MAX_BET_PERCENT)
                .alias("clamped_kelly")
            ]
        )

        value_bets = []
        reasoning_map = reasoning_map or {}

        for row in df.to_dicts():
            advised_stake = (row["clamped_kelly"] / 100.0) * self.bankroll
            confidence = self.get_confidence(row["edge_percent"])

            value_bets.append(
                ValueBet(
                    horse=row["name"],
                    track=race_card.track,
                    race_number=race_card.race_number,
                    race_time=race_card.race_time,
                    odds_decimal=row["odds"],
                    estimated_probability=row["est_prob"],
                    implied_probability=1.0 / row["odds"],
                    edge_percent=round(row["edge_percent"], 2),
                    kelly_stake_percent=round(row["clamped_kelly"], 2),
                    advised_stake=round(advised_stake, 2),
                    confidence=confidence,
                    reasoning=reasoning_map.get(
                        row["name"], "Edge detected via Polars engine"
                    ),
                )
            )

        value_bets.sort(key=lambda vb: vb.edge_percent, reverse=True)
        return value_bets

    def calculate_edge_for_bet(
        self, odds_decimal: float, estimated_probability: float
    ) -> Dict:
        """
        Standalone edge calculation for a single horse.
        Used by the MAF tool `calculate_probability_edge`.
        """
        implied_prob = self.calculate_implied_probability(odds_decimal)
        edge = self.calculate_edge(estimated_probability, odds_decimal)

        return {
            "implied_probability": round(implied_prob, 4),
            "estimated_probability": round(estimated_probability, 4),
            "edge_percent": round(edge, 2),
            "has_value": edge >= self.MIN_EDGE_PERCENT,
            "confidence": self.get_confidence(edge),
            "kelly_stake_percent": self.calculate_kelly_stake(
                estimated_probability, odds_decimal
            ),
        }
