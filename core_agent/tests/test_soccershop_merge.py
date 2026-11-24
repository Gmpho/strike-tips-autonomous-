import pytest
from core_agent.core.adaptive_odds_monitor import _merge_soccershop_into


def test_merge_soccershop_into_hydrates_sp_runner():
    state = {
        "events": {
            "race1": {
                "course": "Fairview Polytrack",
                "runners": [
                    {"name": "Rhydian", "odds": "SP"},
                    {"name": "Mio Destino", "odds": 4.0},
                ],
            }
        }
    }
    ss_snapshot = {
        "events": {
            "ss1": {
                "course": "Fairview Polytrack",
                "runners": [
                    {"name": "RHYDIAN", "odds": 5.0},
                    {"name": "MIO DESTINO", "odds": 4.5},
                ],
            }
        }
    }
    _merge_soccershop_into(state, ss_snapshot)

    runners = state["events"]["race1"]["runners"]
    # SP runner should get hydrated with SoccerShop price
    assert runners[0]["odds"] == 5.0
    assert runners[0]["price_source"] == "soccershop"
    # Already-priced runner keeps its existing Betway price (4.0, not 4.5)
    assert runners[1]["odds"] == 4.0


def test_merge_soccershop_into_empty_or_unmatched():
    state = {
        "events": {
            "race1": {
                "course": "Kenilworth",
                "runners": [{"name": "Horse A", "odds": "SP"}],
            }
        }
    }
    # No matching course
    ss_snapshot = {
        "events": {
            "ss1": {
                "course": "Durbanville",
                "runners": [{"name": "Horse A", "odds": 3.0}],
            }
        }
    }
    _merge_soccershop_into(state, ss_snapshot)
    assert state["events"]["race1"]["runners"][0]["odds"] == "SP"

    # None input resilience
    _merge_soccershop_into(None, None)
    _merge_soccershop_into(state, None)
