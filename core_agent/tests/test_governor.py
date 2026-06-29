import os
import json
import shutil
import pytest
from core_agent.skills.bankroll_manager.governor import BankrollGovernor, BetRecord

@pytest.fixture
def temp_data_dir(tmp_path):
    d = tmp_path / "data"
    d.mkdir()
    return str(d)

def test_governor_initialization(temp_data_dir):
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    assert gov.current_bankroll == 1000.0
    assert gov.drawdown_percent == 0.0
    assert len(gov.get_open_bets()) == 0

def test_calculate_max_stake(temp_data_dir):
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    # Edge < 5% should return 0
    assert gov.calculate_max_stake(4.9) == 0.0
    
    # Half-Kelly for 10% edge: 1000 * 0.10 * 0.5 = 50.0
    # Capped at 5% of bankroll: 1000 * 0.05 = 50.0
    assert gov.calculate_max_stake(10.0) == 50.0

    # Half-Kelly for 20% edge: 1000 * 0.20 * 0.5 = 100.0
    # Capped at 5% of bankroll: 1000 * 0.05 = 50.0
    assert gov.calculate_max_stake(20.0) == 50.0

    # Half-Kelly for 6% edge: 1000 * 0.06 * 0.5 = 30.0
    assert gov.calculate_max_stake(6.0) == 30.0

def test_record_and_settle_bet(temp_data_dir):
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    
    # Record a pending bet
    bet = gov.record_bet(
        track="Greyville",
        race_number=1,
        horse="Stormy",
        odds=3.0,
        stake=50.0,
        edge_percent=10.0,
        confidence="HIGH"
    )
    
    assert bet is not None
    assert bet.status == "PENDING"
    assert bet.stake == 50.0
    assert gov.get_open_exposure() == 50.0
    assert len(gov.get_open_bets()) == 1
    
    # Settle the bet as WON (odds 3.0, return is 150)
    success = gov.settle_bet(bet.bet_id, won=True, notes="Won race")
    assert success is True
    
    # Bankroll updates: 1000.0 + (150.0 - 50.0) = 1100.0
    assert gov.current_bankroll == 1100.0
    assert gov.total_profit_loss == 100.0
    assert gov.get_open_exposure() == 0.0
    assert len(gov.get_open_bets()) == 0

def test_daily_loss_limit_with_exposure(temp_data_dir):
    # Set starting bankroll = 1000.0, daily loss limit = 20% (R200.0)
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    
    # Place multiple pending bets to reach the exposure limit
    # Bet 1: R40.0
    bet1 = gov.record_bet("Vaal", 1, "Horse A", 2.0, 40.0, 10.0, "HIGH")
    # Bet 2: R40.0
    bet2 = gov.record_bet("Vaal", 2, "Horse B", 2.0, 40.0, 10.0, "HIGH")
    # Bet 3: R40.0
    bet3 = gov.record_bet("Vaal", 3, "Horse C", 2.0, 40.0, 10.0, "HIGH")
    # Bet 4: R40.0
    bet4 = gov.record_bet("Vaal", 4, "Horse D", 2.0, 40.0, 10.0, "HIGH")
    
    assert gov.get_open_exposure() == 160.0
    
    # Next bet of R50 should push total at-risk to 210.0, which breaches the 20% limit (R200.0)
    bet5 = gov.record_bet("Vaal", 5, "Horse E", 2.0, 50.0, 10.0, "HIGH")
    assert bet5 is None  # Blocked!
    
    # Settle Bet 1 as LOST (R40 loss)
    gov.settle_bet(bet1.bet_id, won=False)
    # Current bankroll = 960.0. Limit = 192.0.
    # Total loss today is R40, open exposure is R120. Total at-risk: R160.
    
    # Try recording R40 bet again (pushes total at-risk to 200, exceeding 192 limit)
    bet6 = gov.record_bet("Vaal", 5, "Horse F", 2.0, 40.0, 10.0, "HIGH")
    assert bet6 is None  # Blocked!
    
    # Try recording a small R10 bet (R170 total at risk, under 192 limit)
    bet7 = gov.record_bet("Vaal", 5, "Horse G", 2.0, 10.0, 10.0, "HIGH")
    assert bet7 is not None  # Allowed!

def test_generate_daily_report(temp_data_dir):
    gov = BankrollGovernor(data_dir=temp_data_dir, starting_bankroll=1000.0)
    
    # Place a bet
    bet = gov.record_bet("Vaal", 1, "Horse A", 3.0, 50.0, 10.0, "HIGH")
    assert bet is not None
    
    # Settle it as WON (returns 150, profit = 100)
    gov.settle_bet(bet.bet_id, won=True)
    
    # Place another bet (remains pending)
    pending_bet = gov.record_bet("Vaal", 2, "Horse B", 4.0, 40.0, 12.0, "HIGH")
    assert pending_bet is not None
    
    # Generate the report
    report = gov.generate_daily_report()
    
    assert "DAILY REPORT FOR" in report
    assert "Bankroll Balance : R1100.00" in report
    assert "Total P&L        : +R100.00" in report
    assert "Today's Settled Bets:" in report
    assert "Horse A" in report
    assert "Today's Open Bets:" in report
    assert "Horse B" in report
