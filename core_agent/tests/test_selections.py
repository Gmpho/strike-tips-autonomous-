import os
import json
from datetime import datetime
from core_agent.core.adaptive_odds_monitor import _merge_daily_scan_into
from core_agent.config.paths import DATA_DIR

def test_merge_daily_scan_into():
    # Construct a mock state with 1 event and 3 runners
    state = {
        "events": {
            "greyville_r1": {
                "course": "Greyville",
                "raceNumber": 1,
                "runners": [
                    {"name": "Horse A", "odds": 4.5},
                    {"name": "Horse B", "odds": 2.0},
                    {"name": "Horse C", "odds": 12.0}
                ]
            }
        }
    }
    
    # 1. Test when daily scan file does not exist
    # It should still calculate Favourite and Outsider
    _merge_daily_scan_into(state)
    
    event = state["events"]["greyville_r1"]
    assert "aiSelections" in event
    selections = event["aiSelections"]
    assert selections["value"]["name"] == "Horse A"  # fallback to first
    assert selections["favourite"]["name"] == "Horse B"  # lowest odds
    assert selections["outsider"]["name"] == "Horse C"  # highest odds

    # 2. Test when daily scan file exists with matching value bets
    today_str = datetime.now().strftime("%Y-%m-%d")
    scan_file = os.path.join(str(DATA_DIR), f"daily_scan_{today_str}.json")
    
    mock_scan_data = {
        "greyville": [
            {
                "race_number": 1,
                "value_bets": [
                    {
                        "horse": "Horse C",
                        "edge_percent": 15.0,
                        "odds_decimal": 12.0,
                        "estimated_probability": 0.20
                    }
                ]
            }
        ]
    }
    
    try:
        with open(scan_file, "w") as f:
            json.dump(mock_scan_data, f)
            
        # Re-run merge
        _merge_daily_scan_into(state)
        
        event = state["events"]["greyville_r1"]
        selections = event["aiSelections"]
        assert selections["value"]["name"] == "Horse C"  # matched as value bet
        assert selections["favourite"]["name"] == "Horse B"  # lowest odds
        assert selections["outsider"]["name"] == "Horse C"  # matched as outsider (odds >= 8.0)
        
    finally:
        if os.path.exists(scan_file):
            os.remove(scan_file)
