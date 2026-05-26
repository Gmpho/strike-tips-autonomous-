import asyncio
import os
import json
import shutil
import logging
from core_agent.skills.bankroll_manager.governor import BankrollGovernor

# Setup logging to see what's happening
logging.basicConfig(level=logging.INFO)

async def sim_bet(data_dir, horse_name):
    # Simulate a separate process/container starting up
    gov = BankrollGovernor(data_dir=data_dir, starting_bankroll=1000.0)
    print(f"[{horse_name}] Governor initialized. Balance: {gov.current_bankroll}")
    # Simulate some work
    await asyncio.sleep(0.1)
    bet = gov.record_bet(
        track="ReproTrack",
        race_number=1,
        horse=horse_name,
        odds=2.0,
        stake=50.0,
        edge_percent=10.0,
        confidence="HIGH"
    )
    if bet:
        print(f"[{horse_name}] Bet recorded: {bet.bet_id}")
    else:
        print(f"[{horse_name}] Bet FAILED to record")

async def main():
    test_dir = "./repro_data"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)

    print("--- Starting Concurrent Bet Simulation ---")
    # Run two bet operations concurrently
    await asyncio.gather(
        sim_bet(test_dir, "Horse A"),
        sim_bet(test_dir, "Horse B")
    )

    # Check results
    state_file = os.path.join(test_dir, "bankroll_state.json")
    if os.path.exists(state_file):
        with open(state_file) as f:
            state = json.load(f)
        print(f"Final Bankroll: {state['current_bankroll']}")
    else:
        print("❌ Final state file NOT FOUND")
    
    bets_file = os.path.join(test_dir, "bet_history.json")
    if os.path.exists(bets_file):
        with open(bets_file) as f:
            bets = json.load(f)
        print(f"Total Bets in History: {len(bets)}")
    else:
        print("❌ Bet history file NOT FOUND")

if __name__ == "__main__":
    asyncio.run(main())
