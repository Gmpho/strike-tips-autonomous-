import pytest
from core_agent.tools.maf_tool_registry import (
    extract_form_string,
    detect_jockey_trainer,
    get_jockey_trainer_multiplier,
    compute_win_probability,
    build_exotics_blueprint,
    analyze_full_race_card
)

def test_extract_form_string():
    # Test parenthesis extraction
    assert extract_form_string("#5 Act Of Grace (60.5kg) (2-247-217)") == "2-247-217"
    assert extract_form_string("#10 Sommerstern (60.5kg) won last start (21-1321)") == "21-1321"
    
    # Test keyword 'form' extraction
    assert extract_form_string("#10 Double Grand Slam (60kg) - 5yo, form 11-4112") == "11-4112"
    
    # Test fallback extraction of long sequences
    assert extract_form_string("#2 Town Crier (60kg) - 3yo, form 143891") == "143891"

def test_detect_jockey_trainer():
    # Test 'Trainer X, jockey Y' format
    jockey, trainer = detect_jockey_trainer("Trainer Glen Kotzen, jockey Chad Little – flying.")
    assert jockey == "Chad Little"
    assert trainer == "Glen Kotzen"
    
    # Test 'jockey/trainer' format
    jockey, trainer = detect_jockey_trainer("Justin Snaith/R Fourie")
    assert jockey == "R Fourie"
    assert trainer == "Justin Snaith"
    
    # Test keyword fallback matching
    jockey, trainer = detect_jockey_trainer("Calvin Habib on a Sean Tarry runner")
    assert jockey == "Habib"
    assert trainer == "Tarry"

def test_get_jockey_trainer_multiplier():
    assert get_jockey_trainer_multiplier("Fourie", "Snaith") == 1.10
    assert get_jockey_trainer_multiplier("Unknown", "Unknown") == 1.00

def test_compute_win_probability():
    prob = compute_win_probability("1-2-1", 60.5, "Fourie", "Snaith", 10)
    assert 0.01 <= prob <= 0.75

def test_build_exotics_blueprint():
    # Construct simulated races
    races = [
        {
            "number": 1,
            "runners": [{"number": 1, "name": "H1", "weight": 58, "jockey": "", "trainer": "", "form": "111", "prob": 0.3}],
            "pools": ["JP1"],
            "header": "Race 1 (JP1 Leg 1)"
        },
        {
            "number": 2,
            "runners": [{"number": 2, "name": "H2", "weight": 58, "jockey": "", "trainer": "", "form": "111", "prob": 0.3}],
            "pools": ["BI1"],
            "header": "Race 2 (BI1 Leg 1)"
        },
        {
            "number": 3,
            "runners": [{"number": 3, "name": "H3", "weight": 58, "jockey": "", "trainer": "", "form": "111", "prob": 0.3}],
            "pools": ["PA"],
            "header": "Race 3 (PA Leg 1)"
        },
        {
            "number": 4,
            "runners": [{"number": 4, "name": "H4", "weight": 58, "jockey": "", "trainer": "", "form": "111", "prob": 0.3}],
            "pools": ["P6"],
            "header": "Race 4 (P6 Leg 1)"
        }
    ]
    
    blueprints, starts = build_exotics_blueprint(races)
    
    assert starts["JP1"] == 1
    assert starts["BI1"] == 2
    assert starts["PA"] == 3
    assert starts["P6"] == 4

@pytest.mark.asyncio
async def test_analyze_full_race_card():
    card = """
Race 1 – 11:45 (JP1 Leg 1)
#5 Act Of Grace (60.5kg) – trainer Glen Kotzen, jockey Chad Little (2-247-217)
#10 Sommerstern (60.5kg) – Callan Murray up, Lucinda Woodruff (21-1321)

Race 2 – 12:25 (BI1 Leg 1)
#5 Imilenzeyokududuma (59.5kg) – S Veale/G Puller (6-54542)
#3 Magic Verse (60.5kg) – Justin Snaith/Zac Lloyd (5-25944)
"""
    result = await analyze_full_race_card(card)
    assert result["status"] == "success"
    assert "STRIKE TIPS L7 RACE ANALYSIS" in result["report"]
    assert "Detected Pool Starts" in result["report"]
