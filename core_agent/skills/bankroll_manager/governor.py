"""
Bankroll Governor - Disciplined Staking Enforcer
Enforces hard limits: 5% max per bet, 20% daily loss limit.
Persists bet history to JSON for full auditability.
"""

import json
import logging
import os
import uuid
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import List, Optional, Dict

logger = logging.getLogger("bankroll-governor")


@dataclass
class BetRecord:
    """Individual bet record"""
    bet_id: str
    timestamp: str
    date: str
    track: str
    race_number: int
    horse: str
    odds: float
    stake: float
    potential_return: float
    status: str  # PENDING, WON, LOST
    edge_percent: float
    confidence: str
    actual_return: Optional[float] = None
    profit_loss: Optional[float] = None
    notes: str = ""


@dataclass
class DailyStats:
    """Daily aggregation statistics"""
    date: str
    bets_placed: int = 0
    total_staked: float = 0.0
    total_returned: float = 0.0
    profit_loss: float = 0.0
    wins: int = 0
    losses: int = 0

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        return self.wins / total if total > 0 else 0.0

    @property
    def roi(self) -> float:
        return (self.profit_loss / self.total_staked * 100.0) if self.total_staked > 0 else 0.0


class BankrollGovernor:
    """
    Bankroll discipline enforcer.

    Hard Limits (non-negotiable):
    - Max 5% of bankroll per single bet
    - Stop if daily loss exceeds 20% of bankroll
    - Stop if drawdown exceeds 50% from peak
    - Only place bets with 5%+ edge
    """

    MAX_BET_PERCENT: float = 5.0
    DAILY_LOSS_LIMIT_PERCENT: float = 20.0
    MAX_DRAWDOWN_PERCENT: float = 50.0
    MIN_EDGE_PERCENT: float = 5.0
    KELLY_FRACTION: float = 0.5

    def __init__(self, data_dir: str = "./data", starting_bankroll: float = 1000.0):
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)

        self._state_file = os.path.join(self.data_dir, "bankroll_state.json")
        self._bets_file = os.path.join(self.data_dir, "bet_history.json")

        self._bets: List[BetRecord] = []
        self._load_state(starting_bankroll)

    # ─── Persistence ────────────────────────────────────────────────────────

    def _load_state(self, starting_bankroll: float):
        """Load persisted bankroll state"""
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file) as f:
                    state = json.load(f)
                self.current_bankroll = state.get("current_bankroll", starting_bankroll)
                self.peak_bankroll = state.get("peak_bankroll", starting_bankroll)
                self.total_profit_loss = state.get("total_profit_loss", 0.0)
            except Exception as e:
                logger.warning(f"Could not load bankroll state: {e}")
                self.current_bankroll = starting_bankroll
                self.peak_bankroll = starting_bankroll
                self.total_profit_loss = 0.0
        else:
            self.current_bankroll = starting_bankroll
            self.peak_bankroll = starting_bankroll
            self.total_profit_loss = 0.0

        if os.path.exists(self._bets_file):
            try:
                with open(self._bets_file) as f:
                    raw_bets = json.load(f)
                self._bets = [BetRecord(**b) for b in raw_bets]
            except Exception as e:
                logger.warning(f"Could not load bet history: {e}")
                self._bets = []

    def _save_state(self):
        """Persist bankroll state and bet history"""
        try:
            with open(self._state_file, "w") as f:
                json.dump({
                    "current_bankroll": self.current_bankroll,
                    "peak_bankroll": self.peak_bankroll,
                    "total_profit_loss": self.total_profit_loss,
                    "last_updated": datetime.now().isoformat(),
                }, f, indent=2)

            with open(self._bets_file, "w") as f:
                json.dump([asdict(b) for b in self._bets], f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    # ─── Computed Properties ────────────────────────────────────────────────

    @property
    def drawdown_percent(self) -> float:
        if self.peak_bankroll <= 0:
            return 0.0
        return ((self.peak_bankroll - self.current_bankroll) / self.peak_bankroll) * 100.0

    # ─── Limit Checks ───────────────────────────────────────────────────────

    def can_bet_today(self) -> tuple[bool, str]:
        """Check if betting is allowed today"""
        today_stats = self.get_today_stats()
        daily_loss = -today_stats.profit_loss

        if daily_loss >= self.current_bankroll * (self.DAILY_LOSS_LIMIT_PERCENT / 100.0):
            return False, f"Daily loss limit reached ({self.DAILY_LOSS_LIMIT_PERCENT}%)"

        if self.drawdown_percent >= self.MAX_DRAWDOWN_PERCENT:
            return False, f"Max drawdown reached ({self.MAX_DRAWDOWN_PERCENT}%)"

        return True, "OK"

    def calculate_max_stake(self, edge_percent: float) -> float:
        """Calculate maximum allowed stake using Half-Kelly, capped at 5%"""
        if edge_percent < self.MIN_EDGE_PERCENT:
            return 0.0
        edge_fraction = edge_percent / 100.0
        kelly_stake = self.current_bankroll * edge_fraction * self.KELLY_FRACTION
        max_stake = self.current_bankroll * (self.MAX_BET_PERCENT / 100.0)
        return round(min(kelly_stake, max_stake), 2)

    # ─── Bet Operations ─────────────────────────────────────────────────────

    def record_bet(
        self,
        track: str,
        race_number: int,
        horse: str,
        odds: float,
        stake: float,
        edge_percent: float,
        confidence: str,
    ) -> Optional[BetRecord]:
        """Record a new bet after passing all governor checks"""
        can_bet, reason = self.can_bet_today()
        if not can_bet:
            logger.warning(f"Bet blocked by governor: {reason}")
            return None

        if edge_percent < self.MIN_EDGE_PERCENT:
            logger.warning(f"Bet rejected: insufficient edge ({edge_percent}% < {self.MIN_EDGE_PERCENT}%)")
            return None

        max_stake = self.calculate_max_stake(edge_percent)
        if stake > max_stake:
            logger.warning(f"Stake reduced from R{stake:.2f} to R{max_stake:.2f} (governor cap)")
            stake = max_stake

        now = datetime.now()
        bet_id = f"{now.strftime('%Y%m%d%H%M%S')}_{horse[:3].upper()}"

        bet = BetRecord(
            bet_id=bet_id,
            timestamp=now.isoformat(),
            date=date.today().isoformat(),
            track=track,
            race_number=race_number,
            horse=horse,
            odds=odds,
            stake=stake,
            potential_return=round(stake * odds, 2),
            status="PENDING",
            edge_percent=edge_percent,
            confidence=confidence,
        )

        self._bets.append(bet)
        self._save_state()
        logger.info(f"Bet recorded: {horse} @ {odds} for R{stake:.2f} (edge: +{edge_percent}%)")
        return bet

    def settle_bet(self, bet_id: str, won: bool, notes: str = "") -> bool:
        """Settle a pending bet with a result"""
        bet = next((b for b in self._bets if b.bet_id == bet_id), None)
        if not bet:
            logger.warning(f"Bet not found: {bet_id}")
            return False

        if bet.status != "PENDING":
            logger.warning(f"Bet {bet_id} already settled as {bet.status}")
            return False

        if won:
            actual_return = bet.potential_return
            bet.status = "WON"
        else:
            actual_return = 0.0
            bet.status = "LOST"

        bet.actual_return = actual_return
        bet.profit_loss = actual_return - bet.stake
        bet.notes = notes

        # Update bankroll
        self.current_bankroll += bet.profit_loss
        self.total_profit_loss += bet.profit_loss
        if self.current_bankroll > self.peak_bankroll:
            self.peak_bankroll = self.current_bankroll

        self._save_state()
        logger.info(f"Bet settled: {bet.horse} - {'WON' if won else 'LOST'} | P&L: R{bet.profit_loss:.2f}")
        return True

    # ─── Reporting ───────────────────────────────────────────────────────────

    def get_today_stats(self) -> DailyStats:
        """Get statistics for today"""
        today = date.today().isoformat()
        today_bets = [b for b in self._bets if b.date == today]
        stats = DailyStats(date=today)

        for bet in today_bets:
            stats.bets_placed += 1
            stats.total_staked += bet.stake
            if bet.status in ("WON", "LOST"):
                pl = bet.profit_loss or 0.0
                stats.profit_loss += pl
                stats.total_returned += bet.actual_return or 0.0
                if bet.status == "WON":
                    stats.wins += 1
                else:
                    stats.losses += 1

        return stats

    def get_open_bets(self) -> List[BetRecord]:
        """Return all pending (unsettled) bets"""
        return [b for b in self._bets if b.status == "PENDING"]

    def get_performance_summary(self) -> Dict:
        """Full performance summary with raw numeric values"""
        settled = [b for b in self._bets if b.status in ("WON", "LOST")]
        total_staked = sum(b.stake for b in settled)
        total_pl = sum(b.profit_loss or 0.0 for b in settled)
        wins = sum(1 for b in settled if b.status == "WON")

        return {
            "total_bets": len(settled),
            "wins": wins,
            "losses": len(settled) - wins,
            "win_rate": (wins / len(settled) * 100) if settled else 0.0,
            "total_staked": round(total_staked, 2),
            "total_profit_loss": round(total_pl, 2),
            "roi": (total_pl / total_staked * 100) if total_staked > 0 else 0.0,
        }

    def generate_daily_report(self) -> str:
        """Generate a human-readable daily report"""
        stats = self.get_today_stats()
        perf = self.get_performance_summary()
        open_bets = self.get_open_bets()

        return (
            f"\n{'='*50}\n"
            f"STRIKE TIPS - Daily Report ({date.today().isoformat()})\n"
            f"{'='*50}\n"
            f"Bankroll: R{self.current_bankroll:.2f} "
            f"(Peak: R{self.peak_bankroll:.2f} | Drawdown: {self.drawdown_percent:.1f}%)\n"
            f"\nToday:\n"
            f"  Bets Placed: {stats.bets_placed}\n"
            f"  Total Staked: R{stats.total_staked:.2f}\n"
            f"  P&L: R{stats.profit_loss:.2f}\n"
            f"  W/L: {stats.wins}/{stats.losses}\n"
            f"\nAll-Time:\n"
            f"  Win Rate: {perf['win_rate']:.1f}%\n"
            f"  ROI: {perf['roi']:.1f}%\n"
            f"  Total P&L: R{perf['total_profit_loss']:.2f}\n"
            f"\nOpen Bets: {len(open_bets)}\n"
            f"{'='*50}\n"
        )
