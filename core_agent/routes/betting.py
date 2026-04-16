"""
Strike Tips - Betting Routes
Endpoints for placing, settling, and managing bets.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from core_agent.core.strike_brain import brain

router = APIRouter(prefix="/api/bets", tags=["betting"])

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

@router.post("")
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
        override_stake=bet.stake
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

@router.get("")
async def get_bets():
    """Get all bets"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    from dataclasses import asdict
    # Return all bets from the internal _bets list in the BankrollGovernor
    # Governor is available at brain.strike.bankroll
    return {"bets": [asdict(b) for b in brain.strike.bankroll._bets]}

@router.get("/open")
async def get_open_bets():
    """Get pending bets"""
    if not brain.strike:
        raise HTTPException(status_code=503, detail="System not initialized")
    from dataclasses import asdict
    return {"bets": [asdict(b) for b in brain.strike.bankroll.get_open_bets()]}
