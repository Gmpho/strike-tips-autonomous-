"""Future-meeting gate + exotic phantom guard (Sep-2026: Thursday Vaal card
harvested on Sunday went out as "turffontein" and took real stakes)."""
import pytest

from core_agent.core.strike_tips import (
    _drop_meetings_not_running_today,
    _norm_text,
    _play_matches_snapshot,
)


def test_norm_text():
    assert _norm_text("Vaal (RSA)") == "vaalrsa"
    assert _norm_text("Scott's Bar") == "scottsbar"


def test_gate_drops_future_meeting():
    all_results = {"vaal": [{"race_number": 1}], "scottsville": [{"race_number": 1}]}
    dates = {"vaal": {"2026-09-17"}, "scottsville": {"2026-09-13"}}
    out = _drop_meetings_not_running_today(dict(all_results), dates, "2026-09-13")
    assert out["vaal"] == []
    assert out["scottsville"] == [{"race_number": 1}]


def test_gate_fails_open_for_unknown_course():
    all_results = {"vaal": [{"race_number": 1}]}
    out = _drop_meetings_not_running_today(dict(all_results), {}, "2026-09-13")
    assert out["vaal"] == [{"race_number": 1}]


def test_gate_keeps_empty_tracks():
    out = _drop_meetings_not_running_today(
        {"turffontein": []}, {"turffontein": {"2026-09-17"}}, "2026-09-13")
    assert out["turffontein"] == []


def _play(track, bankers):
    return {
        "pool": "JP1",
        "_track": track,
        "combinations": [{"race": i + 1, "banker": b, "savers": []}
                         for i, b in enumerate(bankers)],
    }


def test_phantom_play_rejected():
    snap = {"turffontein": {"someotherhorse", "anotherone"}}
    play = _play("turffontein", ["BEACH WALKER", "POLLY PLUMMER"])
    assert _play_matches_snapshot(play, snap) is False


def test_real_play_accepted():
    snap = {"turffontein": {"beachwalker", "pollyplummer", "euphrates"}}
    play = _play("Turffontein", ["BEACH WALKER", "POLLY PLUMMER"])
    assert _play_matches_snapshot(play, snap) is True


def test_play_rejected_when_track_absent_from_snapshot():
    snap = {"scottsville": {"beachwalker", "pollyplummer"}}
    play = _play("turffontein", ["BEACH WALKER", "POLLY PLUMMER"])
    assert _play_matches_snapshot(play, snap) is False


def test_play_with_no_bankers_rejected():
    assert _play_matches_snapshot({"pool": "JP1", "_track": "vaal", "combinations": []},
                                  {"vaal": {"x"}}) is False
