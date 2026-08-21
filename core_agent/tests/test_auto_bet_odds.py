import pytest

from core_agent.core.strike_tips import resolve_auto_bet_odds


def test_extracts_primary_odds_key():
    assert resolve_auto_bet_odds({"odds_decimal": 5.0}) == 5.0


def test_falls_through_alternate_keys():
    assert resolve_auto_bet_odds({"offered_odds": 4.2}) == 4.2
    assert resolve_auto_bet_odds({"bookmaker_odds": "6.5"}) == 6.5
    assert resolve_auto_bet_odds({"odds": 3}) == 3.0


def test_missing_odds_returns_none():
    """Regression: auto-bet previously defaulted to an assumed 2.0."""
    assert resolve_auto_bet_odds({}) is None
    assert resolve_auto_bet_odds({"horse": "Speedy"}) is None


def test_invalid_odds_returns_none():
    assert resolve_auto_bet_odds({"odds": "abc"}) is None
    assert resolve_auto_bet_odds({"odds": None}) is None


def test_placeholder_and_impossible_odds_rejected():
    # 5.0 SP placeholder handled upstream, but sub-1.01 prices are never bettable
    assert resolve_auto_bet_odds({"odds_decimal": 1.0}) is None
    assert resolve_auto_bet_odds({"odds_decimal": 0}) is None
