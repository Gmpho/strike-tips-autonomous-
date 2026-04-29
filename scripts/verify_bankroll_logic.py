
import os
import sys
import shutil

# Add core_agent to path
sys.path.append(os.path.abspath("."))

from core_agent.skills.bankroll_manager.governor import BankrollGovernor

def test_bankroll_limits():
    test_data_dir = "./test_data_bankroll"
    if os.path.exists(test_data_dir):
        shutil.rmtree(test_data_dir)
    os.makedirs(test_data_dir)

    # Start with R1000
    governor = BankrollGovernor(data_dir=test_data_dir, starting_bankroll=1000.0)

    print(f"Initial Bankroll: R{governor.current_bankroll}")

    # 1. Test Min Edge Threshold (5%)
    print("\nTesting Min Edge Threshold...")
    bet = governor.record_bet(
        track="Turffontein",
        race_number=1,
        horse="Slow Horse",
        odds=2.0,
        stake=50.0,
        edge_percent=3.0, # Below 5%
        confidence="MARGINAL"
    )
    assert bet is None
    print("OK: Bet with 3% edge was rejected.")

    # 2. Test Max Bet Limit (5% of R1000 = R50)
    print("\nTesting Max Bet Limit (5%)...")
    bet = governor.record_bet(
        track="Turffontein",
        race_number=2,
        horse="Fast Horse",
        odds=10.0,
        stake=100.0, # Requested R100
        edge_percent=15.0,
        confidence="STRONG_VALUE"
    )
    assert bet is not None
    assert bet.stake == 50.0 # Should be capped at R50 (5% of R1000)
    print(f"OK: Stake capped at R{bet.stake} (5% of R1000).")

    # Settle it to continue with clean state
    governor.settle_bet(bet.bet_id, won=False)
    # Bankroll now 950.0

    # 3. Test Kelly Staking
    # Edge 10%, Odds 5.0
    # kelly_stake = 950 * 0.10 * 0.5 = 47.5
    # max_stake = 950 * 0.05 = 47.5
    print("\nTesting Kelly Staking...")
    max_stake = governor.calculate_max_stake(10.0)
    print(f"Max stake for 10% edge: R{max_stake}")
    assert max_stake == 47.5

    # Edge 6%
    # kelly_stake = 950 * 0.06 * 0.5 = 28.5
    max_stake = governor.calculate_max_stake(6.0)
    print(f"Max stake for 6% edge: R{max_stake}")
    assert max_stake == 28.5

    # 4. Test Daily Loss Limit (20% of current bankroll)
    print("\nTesting Daily Loss Limit...")
    # Record and lose bets until we hit limit
    count = 0
    while True:
        can_bet, _ = governor.can_bet_today()
        if not can_bet:
            print(f"Daily limit reached after {count} losing bets.")
            break
        max_s = governor.calculate_max_stake(10.0)
        bet = governor.record_bet("Vaal", 1, f"Loser {count}", 2.0, max_s, 10.0, "VALUE")
        if not bet:
            print(f"Daily limit reached (record_bet rejected) after {count} losing bets.")
            break
        governor.settle_bet(bet.bet_id, won=False)
        count += 1

    print(f"Final Bankroll: R{governor.current_bankroll}")

    can_bet, reason = governor.can_bet_today()
    print(f"Can bet today? {can_bet} ({reason})")
    assert can_bet is False
    assert "Daily loss limit reached" in reason

    shutil.rmtree(test_data_dir)
    print("\nBankroll Logic Audit Complete.")

if __name__ == "__main__":
    test_bankroll_limits()
