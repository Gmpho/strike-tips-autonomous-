"""
Bankroll Governor - Disciplined Staking Enforcer
Enforces hard limits: 5% max per bet, 20% daily loss limit.
Persists bet history to JSON for full auditability.
"""

import json
import logging
import os
import uuid
import fcntl
import time
from dataclasses import dataclass, asdict, field
from datetime import date, datetime
from typing import List, Optional, Dict, Generator
from contextlib import contextmanager

def _load_paper_settings(data_dir: str) -> dict:
    """Read paper_mode and paper_balance from settings.json"""
    path = os.path.join(data_dir, "settings.json")
    if os.path.exists(path):
        try:
            with open(path) as f:
                s = json.load(f)
            return {"paper_mode": s.get("paper_mode", False), "paper_balance": s.get("paper_balance", 1000.0)}
        except Exception:
            pass
    return {"paper_mode": False, "paper_balance": 1000.0}


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
    status: str
    edge_percent: float
    confidence: str
    distance: Optional[int] = None
    actual_return: Optional[float] = None
    profit_loss: Optional[float] = None
    notes: str = ""
    is_paper: bool = False


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
        return (
            (self.profit_loss / self.total_staked * 100.0)
            if self.total_staked > 0
            else 0.0
        )


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
    MAX_EXOTIC_COST: float = 200.0  # Max R200 per exotic pool ticket

    def __init__(self, data_dir: str = "./data", starting_bankroll: float = 1000.0):
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)

        self._state_file = os.path.join(self.data_dir, "bankroll_state.json")
        self._bets_file = os.path.join(self.data_dir, "bet_history.json")
        self._lock_file = os.path.join(self.data_dir, "bankroll.lock")

        self._bets: List[BetRecord] = []
        self._starting_bankroll = starting_bankroll
        self._load_state(starting_bankroll)

    # ─── Persistence ────────────────────────────────────────────────────────

    @contextmanager
    def _atomic_transaction(self) -> Generator[None, None, None]:
        """
        Context manager for thread-safe and process-safe state modifications.
        1. Acquire exclusive file lock
        2. Reload state from disk
        3. Yield to the operation
        4. Save updated state back to disk
        5. Release lock
        """
        lock_fd = open(self._lock_file, "w")
        try:
            # Block until lock is acquired
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            
            # Reload state to ensure we have the absolute latest from disk
            self._load_state(self._starting_bankroll)
            
            yield
            
            # Save updated state
            self._save_state()
            
        finally:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            lock_fd.close()

    def _load_state(self, starting_bankroll: float):
        """Load persisted bankroll state"""
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file) as f:
                    state = json.load(f)
                self.current_bankroll = state.get("current_bankroll", starting_bankroll)
                self.peak_bankroll = state.get("peak_bankroll", starting_bankroll)
                self.total_profit_loss = state.get("total_profit_loss", 0.0)
                self.paper_balance = state.get("paper_balance", 1000.0)
            except Exception as e:
                logger.warning(f"Could not load bankroll state: {e}")
                self.current_bankroll = starting_bankroll
                self.peak_bankroll = starting_bankroll
                self.total_profit_loss = 0.0
                self.paper_balance = 1000.0
        else:
            self.current_bankroll = starting_bankroll
            self.peak_bankroll = starting_bankroll
            self.total_profit_loss = 0.0
            self.paper_balance = 1000.0

        if os.path.exists(self._bets_file):
            try:
                with open(self._bets_file) as f:
                    raw_bets = json.load(f)
                self._bets = [BetRecord(**b) for b in raw_bets]
            except Exception as e:
                logger.warning(f"Could not load bet history: {e}")
                self._bets = []

    def _save_state(self):
        """Persist bankroll state and bet history atomically"""
        try:
            # 1. Save bankroll_state.json atomically
            state_data = {
                "current_bankroll": self.current_bankroll,
                "peak_bankroll": self.peak_bankroll,
                "total_profit_loss": self.total_profit_loss,
                "paper_balance": self.paper_balance,
                "last_updated": datetime.now().isoformat(),
            }
            tmp_state = self._state_file + ".tmp"
            with open(tmp_state, "w") as f:
                json.dump(state_data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_state, self._state_file)

            # 2. Save bet_history.json atomically
            bets_data = [asdict(b) for b in self._bets]
            tmp_bets = self._bets_file + ".tmp"
            with open(tmp_bets, "w") as f:
                json.dump(bets_data, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_bets, self._bets_file)

        except Exception as e:
            logger.error(f"Failed to save state atomically: {e}")

    # ─── Computed Properties ────────────────────────────────────────────────

    @property
    def drawdown_percent(self) -> float:
        if self.peak_bankroll <= 0:
            return 0.0
        return (
            (self.peak_bankroll - self.current_bankroll) / self.peak_bankroll
        ) * 100.0

    def get_open_exposure(self) -> float:
        """Calculate total stake of currently open/pending bets"""
        return sum(b.stake for b in self.get_open_bets())

    # ─── Limit Checks ───────────────────────────────────────────────────────

    def can_bet_today(self, next_bet_stake: float = 0.0) -> tuple[bool, str]:
        """Check if betting is allowed today, factoring in unsettled exposure and new stake"""
        today_stats = self.get_today_stats()
        daily_loss = -today_stats.profit_loss
        open_exposure = self.get_open_exposure()
        total_at_risk = daily_loss + open_exposure + next_bet_stake

        limit = self.current_bankroll * (self.DAILY_LOSS_LIMIT_PERCENT / 100.0)
        if total_at_risk >= limit:
            return False, f"Daily limit reached (Loss: R{daily_loss:.2f}, Exposure: R{open_exposure:.2f}, New: R{next_bet_stake:.2f} >= Limit: R{limit:.2f})"

        if self.drawdown_percent >= self.MAX_DRAWDOWN_PERCENT:
            return False, f"Max drawdown reached ({self.drawdown_percent:.1f}% >= {self.MAX_DRAWDOWN_PERCENT}%)"

        return True, "OK"

    def calculate_max_stake(
        self,
        edge_percent: float,
        track: Optional[str] = None,
        race_number: Optional[int] = None,
    ) -> float:
        """Calculate maximum allowed stake using Half-Kelly, scaled by Dream Stress Index (DSI)"""
        if edge_percent < self.MIN_EDGE_PERCENT:
            return 0.0
            
        edge_fraction = edge_percent / 100.0
        kelly_stake = self.current_bankroll * edge_fraction * self.KELLY_FRACTION
        
        # Calculate Dream Stress Index (DSI) from ChromaDB simulations
        dsi_scale = 1.0
        if track and race_number is not None:
            try:
                from core_agent.core.strike_brain import brain
                if brain and brain.memory and brain.memory._is_ready:
                    results = brain.memory.search_form_insights(
                        query=f"Scenario simulation for {track} R{race_number}",
                        n_results=10,
                        where={"$and": [{"type": "dream"}, {"track": track.lower()}, {"race": str(race_number)}]}
                    )
                    if results:
                        total_dreams = len(results)
                        neg_dreams = sum(
                            1 for r in results 
                            if r.get("metadata", {}).get("probability_shift", 0.0) < 0.0
                        )
                        dsi = neg_dreams / total_dreams if total_dreams > 0 else 0.0
                        
                        if dsi < 0.20:
                            dsi_scale = 1.0
                        elif dsi <= 0.50:
                            dsi_scale = 0.75
                            logger.info(
                                f"[GOVERNOR] DSI = {dsi*100:.1f}% (moderate stress). "
                                f"Staking scaled by 0.75x"
                            )
                        else:
                            dsi_scale = 0.50
                            logger.info(
                                f"[GOVERNOR] DSI = {dsi*100:.1f}% (high stress under adverse scenarios). "
                                f"Staking scaled by 0.50x (Quarter-Kelly)"
                            )
            except Exception as e:
                logger.warning(f"Failed to query ChromaDB for DSI calculation: {e}")
                
        scaled_kelly = kelly_stake * dsi_scale
        max_stake = self.current_bankroll * (self.MAX_BET_PERCENT / 100.0)
        return round(min(scaled_kelly, max_stake), 2)

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
        distance: Optional[int] = None,
    ) -> Optional[BetRecord]:
        """Record a new bet after passing all governor checks (Atomic)"""
        with self._atomic_transaction():
            # Check paper mode
            paper_settings = _load_paper_settings(self.data_dir)
            is_paper = paper_settings["paper_mode"]

            if edge_percent < self.MIN_EDGE_PERCENT:
                logger.warning(
                    f"Bet rejected: insufficient edge ({edge_percent}% < {self.MIN_EDGE_PERCENT}%)"
                )
                return None

            if is_paper:
                max_stake = self.paper_balance * (self.MAX_BET_PERCENT / 100.0)
            else:
                max_stake = self.calculate_max_stake(edge_percent, track, race_number)
            if stake > max_stake:
                logger.warning(
                    f"Stake reduced from R{stake:.2f} to R{max_stake:.2f} (governor cap)"
                )
                stake = max_stake

            if not is_paper:
                can_bet, reason = self.can_bet_today(stake)
                if not can_bet:
                    logger.warning(f"Bet blocked by governor: {reason}")
                    return None

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
                distance=distance,
                potential_return=round(stake * odds, 2),
                status="PENDING",
                edge_percent=edge_percent,
                confidence=confidence,
                is_paper=is_paper,
            )

            if is_paper:
                bet.notes = "PAPER"
                self.paper_balance -= stake
            
            self._bets.append(bet)
            # _atomic_transaction will handle _save_state()
            
            logger.info(
                f"{'[PAPER] ' if is_paper else ''}Bet recorded: {horse} @ {odds} for R{stake:.2f} (edge: +{edge_percent}%)"
            )
            return bet

    def record_exotic_bet(
        self,
        track: str,
        pool_type: str,
        pool_legs: List[int],
        combinations: List[Dict],
        ticket_cost: float,
        estimated_dividend: float,
    ) -> Optional[BetRecord]:
        """Record an exotic pool bet (Pick 6, Jackpot, Bipot, etc.)"""
        total_cost = len(combinations) * ticket_cost
        if total_cost > self.MAX_EXOTIC_COST:
            logger.warning(f"Exotic cost R{total_cost:.2f} exceeds limit R{self.MAX_EXOTIC_COST:.2f}")
            total_cost = self.MAX_EXOTIC_COST

        with self._atomic_transaction():
            paper_settings = _load_paper_settings(self.data_dir)
            is_paper = paper_settings["paper_mode"]

            if not is_paper:
                can_bet, reason = self.can_bet_today(total_cost)
                if not can_bet:
                    logger.warning(f"Exotic bet blocked by governor: {reason}")
                    return None

            now = datetime.now()
            leg_desc = "-".join(str(r) for r in pool_legs)
            combo_desc = ";".join(
                f"R{c.get('race','?')}#{c.get('banker','?')}" for c in combinations[:3]
            )
            bet_id = f"{now.strftime('%Y%m%d%H%M%S')}_{pool_type[:3]}"

            bet = BetRecord(
                bet_id=bet_id,
                timestamp=now.isoformat(),
                date=date.today().isoformat(),
                track=track,
                race_number=pool_legs[0] if pool_legs else 0,
                horse=f"{pool_type}:{leg_desc}",
                odds=estimated_dividend,
                stake=round(total_cost, 2),
                potential_return=round(total_cost * estimated_dividend, 2),
                status="PENDING",
                edge_percent=0.0,
                confidence="EXOTIC",
                notes=json.dumps({
                    "pool_type": pool_type,
                    "pool_legs": pool_legs,
                    "combinations": combinations,
                    "ticket_cost": ticket_cost,
                }),
                distance=None,
                is_paper=is_paper,
            )

            if is_paper:
                self.paper_balance -= total_cost
            else:
                self.current_bankroll -= total_cost
                self.total_profit_loss -= total_cost

            self._bets.append(bet)
            logger.info(
                f"{'[PAPER] ' if is_paper else ''}Exotic bet recorded: {pool_type} "
                f"Races {leg_desc} for R{total_cost:.2f} ({len(combinations)} combos)"
            )
            return bet

    def settle_exotic_bet(self, bet_id: str, pool_return: float, notes: str = "") -> bool:
        """Settle an exotic pool bet with its actual pool dividend return."""
        with self._atomic_transaction():
            bet = next((b for b in self._bets if b.bet_id == bet_id), None)
            if not bet:
                logger.warning(f"Exotic bet not found: {bet_id}")
                return False
            if bet.status != "PENDING":
                logger.warning(f"Exotic bet {bet_id} already settled as {bet.status}")
                return False

            won = pool_return > 0.0
            if won:
                bet.actual_return = pool_return
                bet.status = "WON"
            else:
                bet.actual_return = 0.0
                bet.status = "LOST"

            bet.profit_loss = (bet.actual_return or 0.0) - bet.stake
            if notes:
                existing = json.loads(bet.notes) if bet.notes else {}
                existing["settlement_notes"] = notes
                bet.notes = json.dumps(existing)

            is_paper_bet = getattr(bet, "is_paper", False) or (bet.notes and "PAPER" in str(bet.notes))
            if is_paper_bet:
                self.paper_balance += (bet.actual_return or 0.0)
            else:
                self.current_bankroll += (bet.actual_return or 0.0) - bet.stake
                self.total_profit_loss += (bet.actual_return or 0.0) - bet.stake

            logger.info(
                f"Exotic bet settled: {bet.horse} - {'WON' if won else 'LOST'} "
                f"| Return: R{bet.actual_return:.2f} | P&L: R{bet.profit_loss:.2f}"
            )
            return True

    def settle_bet(self, bet_id: str, won: bool, notes: str = "") -> bool:
        """Settle a pending bet with a result (Atomic)"""
        with self._atomic_transaction():
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
            is_paper_bet = getattr(bet, "is_paper", False) or (bet.notes and "PAPER" in str(bet.notes))
            if notes:
                bet.notes = f"PAPER | {notes}" if is_paper_bet else notes
            elif is_paper_bet and not bet.notes:
                bet.notes = "PAPER"

            # Update bankroll (paper bets don't affect real balance)
            if is_paper_bet:
                self.paper_balance += actual_return
            else:
                self.current_bankroll += bet.profit_loss
                self.total_profit_loss += bet.profit_loss
                if self.current_bankroll > self.peak_bankroll:
                    self.peak_bankroll = self.current_bankroll

            # _atomic_transaction will handle _save_state()
            
            logger.info(
                f"Bet settled: {bet.horse} - {'WON' if won else 'LOST'} | P&L: R{bet.profit_loss:.2f}"
            )
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

    def generate_daily_report(self) -> str:
        """Generate a structured performance report for the day"""
        today = date.today().isoformat()
        today_stats = self.get_today_stats()
        overall = self.get_performance_summary()
        
        today_bets = [b for b in self._bets if b.date == today]
        settled_today = [b for b in today_bets if b.status in ("WON", "LOST")]
        open_today = [b for b in today_bets if b.status == "PENDING"]
        
        report_lines = [
            f"📅 DAILY REPORT FOR {today}",
            "==========================================",
            f"🏦 Bankroll Balance : R{self.current_bankroll:.2f} (Peak: R{self.peak_bankroll:.2f})",
            f"📈 Total P&L        : {'+' if self.total_profit_loss >= 0 else ''}R{self.total_profit_loss:.2f}",
            "",
            "📊 Today's Performance:",
            "------------------------------------------",
            f"👉 Bets Placed      : {today_stats.bets_placed} (Wins: {today_stats.wins} | Losses: {today_stats.losses})",
            f"💰 Total Staked     : R{today_stats.total_staked:.2f}",
            f"💵 Total Returned   : R{today_stats.total_returned:.2f}",
            f"📉 Net Profit/Loss  : {'+' if today_stats.profit_loss >= 0 else ''}R{today_stats.profit_loss:.2f}",
            "",
            "📊 Lifetime Statistics:",
            "------------------------------------------",
            f"👉 Total Settled    : {overall['total_bets']} (Wins: {overall['wins']} | Losses: {overall['losses']})",
            f"🎯 Win Rate         : {overall['win_rate']:.1f}%",
            f"💸 ROI              : {overall['roi']:.1f}%",
        ]
        
        if settled_today:
            report_lines.append("\n✅ Today's Settled Bets:")
            for b in settled_today:
                res = "WON" if b.status == "WON" else "LOST"
                pl_sign = "+" if (b.profit_loss or 0) >= 0 else ""
                report_lines.append(
                    f"  - R{b.race_number} @ {b.track}: {b.horse} ({b.odds:.1f}x) "
                    f"| Stake: R{b.stake:.2f} | [{res}] {pl_sign}R{b.profit_loss or 0.0:.2f}"
                )
                
        if open_today:
            report_lines.append("\n⏳ Today's Open Bets:")
            for b in open_today:
                report_lines.append(
                    f"  - R{b.race_number} @ {b.track}: {b.horse} ({b.odds:.1f}x) | Stake: R{b.stake:.2f} [PENDING]"
                )
                
        return "\n".join(report_lines)

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

    def get_settled_bets_by_track(self, min_bets: int = 3) -> List[Dict]:
        """Group settled bets by track and return performance metrics per track."""
        settled = [b for b in self._bets if b.status in ("WON", "LOST")]
        from collections import defaultdict
        by_track: Dict[str, List[BetRecord]] = defaultdict(list)
        for b in settled:
            by_track[b.track.lower()].append(b)

        results = []
        for track, bets in by_track.items():
            if len(bets) < min_bets:
                continue
            total_stake = sum(b.stake for b in bets)
            total_pl = sum(b.profit_loss or 0.0 for b in bets)
            wins = sum(1 for b in bets if b.status == "WON")
            roi = (total_pl / total_stake * 100) if total_stake > 0 else 0.0
            results.append({
                "track": track,
                "total_bets": len(bets),
                "wins": wins,
                "losses": len(bets) - wins,
                "win_rate": (wins / len(bets) * 100) if bets else 0.0,
                "total_stake": round(total_stake, 2),
                "profit_loss": round(total_pl, 2),
                "roi": round(roi, 2),
            })
        results.sort(key=lambda r: r["roi"])
        return results

    def get_settled_bets_by_odds_range(self, min_bets: int = 0) -> Dict[str, Dict]:
        """Group settled bets by odds bracket and return performance per bracket."""
        settled = [b for b in self._bets if b.status in ("WON", "LOST")]
        from collections import defaultdict

        def bracket(odds: float) -> str:
            if odds < 2.0:
                return "odds_under_2"
            if odds < 4.0:
                return "odds_2_to_4"
            if odds < 7.0:
                return "odds_4_to_7"
            return "odds_7_plus"

        brackets = ["odds_under_2", "odds_2_to_4", "odds_4_to_7", "odds_7_plus"]
        by_bracket: Dict[str, List[BetRecord]] = defaultdict(list)
        for b in settled:
            by_bracket[bracket(b.odds)].append(b)

        results = {}
        for bracket_name in brackets:
            bets = by_bracket[bracket_name]
            total_stake = sum(b.stake for b in bets)
            total_returned = sum(b.actual_return or 0.0 for b in bets)
            total_pl = sum(b.profit_loss or 0.0 for b in bets)
            wins = sum(1 for b in bets if b.status == "WON")
            total = len(bets)
            roi = (total_pl / total_stake * 100) if total_stake > 0 else 0.0
            results[bracket_name] = {
                "bracket": bracket_name,
                "roi": round(roi, 1),
                "wins": wins,
                "losses": total - wins,
                "total": total,
                "total_bets": total,
                "staked": round(total_stake, 2),
                "returned": round(total_returned, 2),
                "win_rate": round((wins / total * 100) if total else 0.0, 1),
            }
        return results

    def get_history_stats(self, days: int = 15) -> List[Dict]:
        """Return cumulative profit/loss history for charting"""
        from collections import defaultdict
        daily_pl = defaultdict(float)
        
        for bet in self._bets:
            if bet.status in ("WON", "LOST"):
                daily_pl[bet.date] += (bet.profit_loss or 0.0)
                
        # Sort dates and calculate cumulative
        sorted_dates = sorted(daily_pl.keys())[-days:]
        history = []
        cumulative = 0.0
        
        for d in sorted_dates:
            cumulative += daily_pl[d]
            history.append({
                "date": d,
                "pnl": round(cumulative, 2),
                "daily_gain": round(daily_pl[d], 2)
            })
            
        return history
