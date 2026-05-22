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

router = APIRouter(tags=["betting"])

DATA_DIR = os.environ.get("DATA_DIR", "data")


def _load_json(filename: str) -> Any:
    """Load JSON from data directory"""
    path = os.path.join(DATA_DIR, filename)
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
    result = brain.strike.place_bet(
        track=bet.track,
        race_number=bet.race_number,
        horse=bet.horse,
        odds=bet.odds,
        edge_percent=bet.edge_percent,
        confidence=bet.confidence,
        override_stake=bet.stake,
    )
    if result:
        return {"success": True, "bet": result}
    raise HTTPException(status_code=400, detail="Failed to place bet")


@router.post("/settle")
async def settle_bet(request: BetSettleRequest):
    """Settle a bet"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    result = brain.strike.settle_bet(request.bet_id, request.won, request.notes or "")
    return {"success": True, "result": result}


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

    # Filter for pending bets (not WON or LOST)
    pending = [b for b in bets_data if b.get("status") not in ["WON", "LOST"]]

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
    """Get daily/all-time betting statistics"""
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
    wins = sum(1 for b in bets_data if b.get("status") == "WON")
    losses = sum(1 for b in bets_data if b.get("status") == "LOST")
    stake_total = sum(b.get("stake", 0.0) for b in bets_data)
    payout_total = sum(
        b.get("actual_return", 0.0) for b in bets_data if b.get("status") == "WON"
    )
    roi = ((payout_total - stake_total) / stake_total * 100) if stake_total > 0 else 0.0

    return {
        "totalBets": total_bets,
        "wins": wins,
        "losses": losses,
        "stakeTotal": stake_total,
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
    return {"roiByTrack": roi, "accuracy": accuracy}


@router.get("/bankroll-history")
async def get_bankroll_history():
    """Return running bankroll balance over time from bet history"""
    bets_data = _load_json("bet_history.json") or []
    state = _load_json("bankroll_state.json") or {}
    settled = sorted(
        [b for b in bets_data if b.get("status") in ("WON", "LOST")],
        key=lambda b: b.get("timestamp", "")
    )
    current = state.get("current_bankroll", 1000.0)
    total_pl = sum((b.get("actual_return", 0) or 0) - b.get("stake", 0) for b in settled)
    starting = current - total_pl
    points = [{"t": "Start", "balance": round(starting, 2)}]
    running = starting
    for b in settled:
        running += (b.get("actual_return", 0) or 0) - b.get("stake", 0)
        points.append({"t": b.get("timestamp", "")[:10], "balance": round(running, 2)})
    return {"history": points}


@router.get("/bankroll")
@router.get("/account-summary")
async def get_bankroll_state():
    """Get current bankroll state - reads from bankroll_state.json"""
    data = _load_json("bankroll_state.json")
    if not data:
        return {
            "balance": 1000.0,
            "dailyLimit": 200.0,
            "dailyLoss": 0.0,
            "maxStake": 50.0,
            "totalExposure": 0.0,
        }

    # Use brain if available for more accurate data
    if brain and brain.strike and brain.strike.bankroll:
        bankroll = brain.strike.bankroll
        today_stats = bankroll.get_today_stats()
        open_bets = bankroll.get_open_bets()
        total_exposure = sum(b.stake for b in open_bets)
        # Load paper settings
        import json as _json
        _settings_path = os.path.join(DATA_DIR, "settings.json")
        _settings = {}
        if os.path.exists(_settings_path):
            try:
                with open(_settings_path) as _f:
                    _settings = _json.load(_f)
            except Exception:
                pass

        result = BankrollState(
            balance=bankroll.current_bankroll,
            dailyLimit=bankroll.current_bankroll
            * (bankroll.DAILY_LOSS_LIMIT_PERCENT / 100.0),
            dailyLoss=(
                abs(today_stats.profit_loss) if today_stats.profit_loss < 0 else 0.0
            ),
            maxStake=bankroll.current_bankroll * (bankroll.MAX_BET_PERCENT / 100.0),
            totalExposure=total_exposure,
        ).model_dump(by_alias=True)
        result["paperMode"] = _settings.get("paper_mode", False)
        result["paperBalance"] = getattr(bankroll, "paper_balance", _settings.get("paper_balance", 1000.0))
        return result

    # Fallback to JSON file
    return {
        "balance": data.get("current_bankroll", 1000.0),
        "dailyLimit": 200.0,
        "dailyLoss": abs(data.get("total_profit_loss", 0.0)),
        "maxStake": 50.0,
        "totalExposure": 0.0,
    }
