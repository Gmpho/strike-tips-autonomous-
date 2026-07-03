import pytest
from core_agent.skills.exotics import (
    extract_form_string,
    detect_jockey_trainer,
    get_jockey_trainer_multiplier,
    compute_win_probability,
    build_exotics_blueprint,
)
from core_agent.tools.maf_tool_registry import analyze_full_race_card


def test_extract_form_string():
    assert extract_form_string("#5 Act Of Grace (60.5kg) (2-247-217)") == "2-247-217"
    assert extract_form_string("#10 Sommerstern (60.5kg) won last start (21-1321)") == "21-1321"
    assert extract_form_string("#10 Double Grand Slam (60kg) - 5yo, form 11-4112") == "11-4112"
    assert extract_form_string("#2 Town Crier (60kg) - 3yo, form 143891") == "143891"
    assert extract_form_string("") == ""
    assert extract_form_string("no form data here") == ""


def test_detect_jockey_trainer():
    jockey, trainer = detect_jockey_trainer("Trainer Glen Kotzen, jockey Chad Little – flying.")
    assert jockey == "Chad Little"
    assert trainer == "Glen Kotzen"

    jockey, trainer = detect_jockey_trainer("Justin Snaith/R Fourie")
    assert jockey == "R Fourie"
    assert trainer == "Justin Snaith"

    jockey, trainer = detect_jockey_trainer("Calvin Habib on a Sean Tarry runner")
    assert jockey == "Habib"
    assert trainer == "Tarry"

    jockey, trainer = detect_jockey_trainer("unknown rider")
    assert jockey == ""
    assert trainer == ""


def test_get_jockey_trainer_multiplier():
    assert get_jockey_trainer_multiplier("Fourie", "Snaith") == 1.10
    assert get_jockey_trainer_multiplier("Unknown", "Unknown") == 1.00
    assert get_jockey_trainer_multiplier("Fourie", "Unknown") == 1.05
    assert get_jockey_trainer_multiplier("Unknown", "Snaith") == 1.05


def test_compute_win_probability():
    prob = compute_win_probability("1-2-1", 60.5, "Fourie", "Snaith", 10)
    assert 0.01 <= prob <= 0.75
    # Higher weight reduces probability
    prob_heavy = compute_win_probability("1-2-1", 62.0, "Fourie", "Snaith", 10)
    assert prob_heavy < prob


def test_build_exotics_blueprint():
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
    assert "Jackpot 1" in blueprints
    assert "Bipot 1" in blueprints


def test_pool_detection_exceeds_races():
    """Test that pools exceeding total races are handled gracefully."""
    races = [{"number": i, "runners": [{"number": 1, "name": f"H{i}", "weight": 58, "jockey": "", "trainer": "", "form": "111", "prob": 0.3}], "pools": [], "header": f"Race {i}"} for i in range(1, 6)]
    # 5 races, JP2 starts at race 6 (doesn't exist) — should be omitted
    _, starts = build_exotics_blueprint(races)
    assert "JP2" not in starts


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


def test_exotics_module_reimport():
    """Verify the exotics module re-exports work from maf_tool_registry."""
    from core_agent.tools.maf_tool_registry import extract_form_string as reg_extract
    assert reg_extract("#5 Test (60kg) (1-2-3)") == "1-2-3"


def test_empty_form_empty_return():
    """Edge case: empty form should not crash."""
    prob = compute_win_probability("", 58.0, "", "", 10)
    assert 0.01 <= prob <= 0.75
