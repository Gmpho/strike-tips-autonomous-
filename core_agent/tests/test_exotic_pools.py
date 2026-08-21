import pytest

from core_agent.skills.exotics.builder import resolve_pool_legs


def test_jackpot_code_resolves_to_four_legs():
    assert resolve_pool_legs("JP1") == ("JACKPOT", 4)
    assert resolve_pool_legs("JP2") == ("JACKPOT", 4)


def test_bipot_code_resolves_to_six_legs():
    assert resolve_pool_legs("BI1") == ("BIPOT", 6)
    assert resolve_pool_legs("BI2") == ("BIPOT", 6)


def test_pick6_code_resolves_to_six_legs():
    """Regression: P6 previously fell through substring matching to the
    4-leg Jackpot default."""
    assert resolve_pool_legs("P6") == ("PICK 6", 6)


def test_place_accumulator_resolves_to_seven_legs():
    """Regression: PA previously fell through substring matching to the
    4-leg Jackpot default."""
    assert resolve_pool_legs("PA") == ("PLACE ACCUMULATOR", 7)


def test_unknown_code_defaults_to_jackpot_four_legs():
    assert resolve_pool_legs("XX9") == ("JACKPOT", 4)
    assert resolve_pool_legs("") == ("JACKPOT", 4)
