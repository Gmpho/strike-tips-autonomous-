import pytest
from core_agent.skills.league.scoring import (
    base_points, sp_bonus, score_pick, strike_rate, form_rating,
    value_index, qualifies, decayed, MIN_TIPS_TO_QUALIFY,
)


def test_base_points_min_one():
    assert base_points(0) == 1
    assert base_points(12) == 12


def test_sp_bonus_zero_for_short_sp():
    assert sp_bonus(None) == 0
    assert sp_bonus(1.0) == 0
    assert sp_bonus(1.5) == 3


def test_sp_bonus_capped():
    assert sp_bonus(100) == 40


def test_score_pick_top_four_only():
    # Top 4 score; 5th and worse are zero.
    assert score_pick(12, 2, 3.0, 4.0) == 6
    assert score_pick(12, 3, 3.0, 4.0) == 3
    assert score_pick(12, 4, 3.0, 4.0) == 2  # 12 * 0.125
    assert score_pick(12, 5, 3.0, 4.0) == 0


def test_fourth_place_always_scores_at_least_one():
    # A short field must not round 4th down to nothing.
    assert score_pick(4, 4, 3.0, 4.0) == 1
    assert score_pick(1, 4, 3.0, 4.0) == 1


def test_score_pick_winner():
    assert score_pick(12, 1, 4.5, 5.0) == base_points(12) + sp_bonus(5.0)


def test_score_pick_no_sp_falls_back():
    # sp None -> 0 bonus, base points remain
    assert score_pick(8, 1, 2.0, None) == base_points(8)


def test_strike_rate():
    assert strike_rate(0, 0) == 0.0
    assert strike_rate(3, 10) == 0.3


def test_form_rating_zero_on_empty():
    assert form_rating(0, 5) == 0.0
    assert form_rating(4, 0) == 0.0


def test_form_rating_scale():
    # site avg 4, player 4 -> 50
    assert form_rating(4, 4) == 50.0
    # double -> 100
    assert form_rating(8, 4) == 100.0
    # clamped
    assert form_rating(100, 4) == 100.0


def test_value_index():
    assert value_index(5.0, 5.0) == 100.0
    assert value_index(10.0, 5.0) == 200.0
    assert value_index(0, 5.0) == 0.0


def test_qualifies():
    assert not qualifies(4)
    assert qualifies(5)
    assert qualifies(100)


def test_decayed():
    assert decayed("2026-10-01T00:00:00+00:00", "2026-11-04T00:00:00+00:00") is True
    assert decayed("2026-11-03T00:00:00+00:00", "2026-11-04T00:00:00+00:00") is False
    assert decayed(None, "2026-11-04T00:00:00+00:00") is True