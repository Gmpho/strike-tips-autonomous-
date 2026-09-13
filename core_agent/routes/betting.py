"""
Strike Tips - Betting Routes
Endpoints for placing, settling, and managing bets.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import os
from core_agent.core.strike_brain import brain
from core_agent.models.betting import BetRecord, DailyStats, BankrollState
from core_agent.config.paths import DATA_DIR

router = APIRouter(tags=["betting"])


def _load_json(filename: str) -> Any:
    """Load JSON from data directory"""
    path = str(DATA_DIR / filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


class BetRequest(BaseModel):
    track: str
    race_number: int
    horse: str
    odds: float
    edge_percent: float
    confidence: str
    stake: Optional[float] = None


class BetSettleRequest(BaseModel):
    bet_id: str
    won: bool
    notes: Optional[str] = ""


class BetVoidRequest(BaseModel):
    bet_id: str
    action: str = "void"  # "void" (reverse a wrongful settle -> PENDING+refund)
                          # or "cancel" (scrap a PENDING phantom -> VOID+refund)
    reason: Optional[str] = ""


class BettingRootResponse(BaseModel):
    """Lightweight betting route index for endpoint discovery."""

    service: str
    endpoints: Dict[str, str]


@router.get("/", response_model=BettingRootResponse)
async def get_betting_root():
    """Return the canonical betting endpoint map."""
    return BettingRootResponse(
        service="betting",
        endpoints={
            "history": "/api/betting/history",
            "open": "/api/betting/open",
            "stats": "/api/betting/stats",
            "accountSummary": "/api/betting/account-summary",
            "place": "/api/betting/place",
            "settle": "/api/betting/settle",
        },
    )


@router.post("/place")
async def place_bet(bet: BetRequest):
    """Place a new bet"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    try:
        result = brain.strike.place_bet(
            track=bet.track,
            race_number=bet.race_number,
            horse=bet.horse,
            odds=bet.odds,
            edge_percent=bet.edge_percent,
            confidence=bet.confidence,
            override_stake=bet.stake,
        )
    except Exception as e:
        logger.error(f"Failed to place bet: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to place bet: {e}")
    if result:
        return {"success": True, "bet": result}
    raise HTTPException(status_code=400, detail="Failed to place bet (governor rejected)")


@router.post("/settle")
async def settle_bet(request: BetSettleRequest):
    """Settle a bet"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    try:
        result = brain.strike.settle_bet(request.bet_id, request.won, request.notes or "")
    except Exception as e:
        logger.error(f"Failed to settle bet: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to settle bet: {e}")
    return {"success": True, "result": result}


@router.post("/void")
async def void_bet(request: BetVoidRequest):
    """Admin remediation: reverse a wrongful settlement ("void") or scrap a
    PENDING phantom ticket ("cancel", refunds stake, marks VOID). Keyed by
    the global auth middleware like all /api/* paths."""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    gov = brain.strike.bankroll
    if not gov:
        raise HTTPException(status_code=503, detail="Bankroll not initialized")
    action = (request.action or "void").lower()
    try:
        if action == "cancel":
            ok = gov.cancel_pending_bet(request.bet_id, request.reason or "")
        elif action == "void":
            ok = gov.void_settlement(request.bet_id, request.reason or "")
        else:
            raise HTTPException(status_code=400, detail="action must be 'void' or 'cancel'")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to void bet {request.bet_id}: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to void bet: {e}")
    if not ok:
        raise HTTPException(status_code=404, detail="Bet not found or not eligible")
    return {"success": True, "bet_id": request.bet_id, "action": action}


@router.get("/history")
async def get_bets():
    """Get all bets - reads from bet_history.json"""
    bets_data = _load_json("bet_history.json")
    if not bets_data:
        return {"bets": [], "count": 0}

    # Convert to BetRecord format with camelCase
    bets = []
    for b in bets_data if isinstance(bets_data, list) else []:
        settled = b.get("status") in ["WON", "LOST"]
        won = b.get("status") == "WON" if settled else None
        bets.append(
            BetRecord(
                id=b.get("bet_id", ""),
                track=b.get("track", ""),
                raceNumber=b.get("race_number", 1),
                horse=b.get("horse", ""),
                odds=b.get("odds", 0.0),
                edgePercent=b.get("edge_percent", 0.0),
                stake=b.get("stake", 0.0),
                confidence=b.get("confidence", "VALUE"),
                placedAt=b.get("timestamp", datetime.now().isoformat()),
                settled=settled,
                won=won,
                payout=b.get("actual_return", 0.0) if won else None,
                notes=b.get("notes", ""),
            ).model_dump(by_alias=True, exclude_none=True)
        )
    return {"bets": bets, "count": len(bets)}


@router.get("/open")
async def get_open_bets():
    """Get pending bets (status not WON or LOST)"""
    bets_data = _load_json("bet_history.json")
    if not bets_data or not isinstance(bets_data, list):
        return {"bets": [], "count": 0}

    # Filter for pending bets (VOIDed tickets are terminal, like settled ones)
    pending = [b for b in bets_data if b.get("status") == "PENDING"]

    bets = []
    for b in pending:
        bets.append(
            BetRecord(
                id=b.get("bet_id", ""),
                track=b.get("track", ""),
                raceNumber=b.get("race_number", 1),
                horse=b.get("horse", ""),
                odds=b.get("odds", 0.0),
                edgePercent=b.get("edge_percent", 0.0),
                stake=b.get("stake", 0.0),
                confidence=b.get("confidence", "VALUE"),
                placedAt=b.get("timestamp", datetime.now().isoformat()),
                settled=False,
                notes=b.get("notes", ""),
            ).model_dump(by_alias=True, exclude_none=True)
        )
    return {"bets": bets, "count": len(bets)}


@router.get("/stats")
async def get_bet_stats():
    """Get daily/all-time betting statistics on settled and total bets"""
    bets_data = _load_json("bet_history.json")
    if not bets_data or not isinstance(bets_data, list):
        return {
            "totalBets": 0,
            "wins": 0,
            "losses": 0,
            "stakeTotal": 0.0,
            "payoutTotal": 0.0,
            "roi": 0.0,
        }

    total_bets = len(bets_data)
    settled = [b for b in bets_data if b.get("status") in ("WON", "LOST")]
    wins = sum(1 for b in settled if b.get("status") == "WON")
    losses = sum(1 for b in settled if b.get("status") == "LOST")
    settled_stake_total = sum(b.get("stake", 0.0) for b in settled)
    payout_total = sum(
        b.get("actual_return", 0.0) for b in settled if b.get("status") == "WON"
    )
    all_stake_total = sum(b.get("stake", 0.0) for b in bets_data)
    roi = ((payout_total - settled_stake_total) / settled_stake_total * 100) if settled_stake_total > 0 else 0.0

    return {
        "totalBets": total_bets,
        "settledBets": len(settled),
        "pendingBets": total_bets - len(settled),
        "wins": wins,
        "losses": losses,
        "stakeTotal": settled_stake_total,
        "allStakeTotal": all_stake_total,
        "payoutTotal": payout_total,
        "roi": round(roi, 2),
    }


@router.get("/learning/roi-by-track")
async def get_roi_by_track():
    """Get ROI grouped by track + accuracy vs implied probability"""
    roi = {}
    if brain and brain.strike and brain.strike.learning:
        roi = brain.strike.learning.get_roi_summary()
    bets_data = _load_json("bet_history.json") or []
    settled = [b for b in bets_data if b.get("status") in ("WON", "LOST")]
    accuracy = 0.0
    if settled:
        wins = sum(1 for b in settled if b.get("status") == "WON")
        actual_wr = wins / len(settled)
        avg_implied = sum(1.0 / max(b.get("odds", 1.0), 1.01) for b in settled) / len(settled)
        accuracy = round((actual_wr - avg_implied) * 100, 1)

    # Fallback to direct calculation from settled bets if learning summary is empty
    if not roi and settled:
        track_stats: dict[str, dict] = {}
        for b in settled:
            t = b.get("track", "").lower()
            if not t:
                continue
            if t not in track_stats:
                track_stats[t] = {"staked": 0.0, "returned": 0.0}
            track_stats[t]["staked"] += b.get("stake", 0.0)
            if b.get("status") == "WON":
                track_stats[t]["returned"] += b.get("actual_return", 0.0)
        roi = {
            t: round((v["returned"] - v["staked"]) / v["staked"] * 100, 1)
            for t, v in track_stats.items()
            if v["staked"] > 0
        }

    top_track = None
    if roi:
        top_track = max(roi.items(), key=lambda x: x[1])[0]
    elif settled:
        track_counts: dict[str, int] = {}
        for b in settled:
            t = b.get("track", "")
            if t:
                track_counts[t] = track_counts.get(t, 0) + 1
        if track_counts:
            top_track = max(track_counts.items(), key=lambda x: x[1])[0]

    return {
        "roiByTrack": roi,
        "accuracy": accuracy,
        "topTrack": top_track.title() if top_track else "Kenilworth",
    }


@router.get("/learning/roi-by-odds-range")
async def get_roi_by_odds_range():
    """Get settled bets ROI and stats grouped by odds range"""
    from collections import defaultdict
    bets_data = _load_json("bet_history.json") or []
    settled = [b for b in bets_data if b.get("status") in ("WON", "LOST")]

    def bracket(odds: float) -> str:
        if odds < 2.0:
            return "odds_under_2"
        if odds < 4.0:
            return "odds_2_to_4"
        if odds < 7.0:
            return "odds_4_to_7"
        return "odds_7_plus"

    groups: dict[str, dict] = defaultdict(
        lambda: {"total": 0, "wins": 0, "staked": 0.0, "returned": 0.0, "roi": 0.0}
    )
    for b in settled:
        b_name = bracket(b.get("odds", 0.0))
        g = groups[b_name]
        g["total"] += 1
        g["staked"] += b.get("stake", 0.0)
        if b.get("status") == "WON":
            g["wins"] += 1
            g["returned"] += b.get("actual_return", 0.0)

    for g in groups.values():
        if g["staked"] > 0:
            g["roi"] = round((g["returned"] - g["staked"]) / g["staked"] * 100, 1)

    return dict(groups)


@router.get("/bankroll-history")
async def get_bankroll_history():
    """Get bankroll balance history points for charts"""
    if brain and brain.strike and brain.strike.bankroll:
        return {"history": brain.strike.bankroll.get_bankroll_history()}

    # Fallback from bet_history.json
    bets_data = _load_json("bet_history.json") or []
    start_balance = 1000.0
    history = [{"t": "Start", "balance": start_balance}]
    running = start_balance
    for b in bets_data:
        if b.get("status") in ("WON", "LOST"):
            running += b.get("profit_loss", 0.0) or 0.0
            history.append({
                "t": b.get("date") or b.get("timestamp", "")[:10],
                "balance": round(running, 2)
            })
    return {"history": history}


@router.get("/bankroll")
@router.get("/account-summary")
async def get_bankroll_state():
    """Get current bankroll state - reads from bankroll_state.json"""
    data = _load_json("bankroll_state.json")
    _settings_path = os.path.join(DATA_DIR, "settings.json")
    _settings = {}
    if os.path.exists(_settings_path):
        try:
            with open(_settings_path) as _f:
                _settings = json.load(_f)
        except Exception:
            pass
    paper_mode = _settings.get("paper_mode", False)

    if not data:
        base_bal = 1000.0
        return {
            "balance": base_bal,
            "dailyLimit": 200.0,
            "dailyLoss": 0.0,
            "maxStake": 50.0,
            "totalExposure": 0.0,
            "paperMode": paper_mode,
            "paperBalance": base_bal,
            "realBalance": base_bal,
        }

    # Use brain if available for more accurate data
    if brain and brain.strike and brain.strike.bankroll:
        bankroll = brain.strike.bankroll
        today_stats = bankroll.get_today_stats()
        # Active exposure only (stale backlog excluded) — matches governor limits.
        total_exposure = bankroll.get_open_exposure()
        active_balance = (
            getattr(bankroll, "paper_balance", _settings.get("paper_balance", 1000.0))
            if paper_mode
            else bankroll.current_bankroll
        )

        result = BankrollState(
            balance=round(active_balance, 2),
            dailyLimit=round(active_balance * (bankroll.DAILY_LOSS_LIMIT_PERCENT / 100.0), 2),
            dailyLoss=round(abs(today_stats.profit_loss) if today_stats.profit_loss < 0 else 0.0, 2),
            maxStake=round(active_balance * (bankroll.MAX_BET_PERCENT / 100.0), 2),
            totalExposure=round(total_exposure, 2),
        ).model_dump(by_alias=True)
        result["paperMode"] = paper_mode
        result["paperBalance"] = getattr(bankroll, "paper_balance", _settings.get("paper_balance", 1000.0))
        result["realBalance"] = bankroll.current_bankroll
        return result

    # Fallback to JSON file
    active_balance = data.get("paper_balance", 1000.0) if paper_mode else data.get("current_bankroll", 1000.0)
    tpl = data.get("total_profit_loss", 0.0)
    daily_loss = abs(tpl) if tpl < 0 else 0.0
    return {
        "balance": round(active_balance, 2),
        "dailyLimit": round(active_balance * 0.20, 2),
        "dailyLoss": round(daily_loss, 2),
        "maxStake": round(active_balance * 0.05, 2),
        "totalExposure": 0.0,
        "paperMode": paper_mode,
        "paperBalance": data.get("paper_balance", 1000.0),
        "realBalance": data.get("current_bankroll", 1000.0),
    }
