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


def test_tips_pool_starts_durbanville():
    from core_agent.core.strike_tips import _tips_pool_starts

    text = (
        "SOUTH AFRICA\nDURBANVILLE\nClose Bet/Races\n"
        "13:07\nBipot (1-6)\nR48\n"
        "13:45\nPA (2-8)\nR18\n"
        "14:20\nPick 6 (3-8)\nR2000\n"
        "14:55\nJackpot 1 (4-7)\nR80\n"
        "15:30\nJackpot 2 (5-8)\nR80\n"
        "INTERNATIONAL\nHAPPY VALLEY\n"
    )
    assert _tips_pool_starts(text, "durbanville") == {
        "BI1": 1, "PA": 2, "P6": 3, "JP1": 4, "JP2": 5,
    }


def test_tips_pool_starts_scoped_to_meeting():
    from core_agent.core.strike_tips import _tips_pool_starts

    text = "DURBANVILLE\nBipot (1-6)\nKELSO\nBipot (2-7)\n"
    assert _tips_pool_starts(text, "kelso") == {"BI1": 2}
    assert _tips_pool_starts(text, "turffontein") == {}


def test_tips_pool_starts_rejects_bad_lengths():
    from core_agent.core.strike_tips import _tips_pool_starts

    # Bipot must span 6; a 5-race range is parse noise, ignored.
    assert _tips_pool_starts("DURBANVILLE\nBipot (2-6)\n", "durbanville") == {}


def test_parse_distance_m():
    from core_agent.skills.parsers.tab4racing import _parse_distance_m

    assert _parse_distance_m(1600) == 1600
    assert _parse_distance_m(None, "R5 1200m Mdn") == 1200
    assert _parse_distance_m("nope", None) is None
    assert _parse_distance_m("50m sprint") is None  # sub-100m guard
    assert _parse_distance_m(None, None) is None


def test_clip_reasoning_sentence_boundary():
    from core_agent.skills.notifications.telegram_bot import _clip_reasoning

    short = "Fine as is."
    assert _clip_reasoning(short) == short
    long_text = "First sentence here. Second sentence goes on a bit longer than needed for the test. Third."
    clipped = _clip_reasoning(long_text, limit=60)
    assert clipped.endswith("…")
    assert "Third" not in clipped
    assert clipped.startswith("First sentence here.")


def test_bf_form_index_and_brief(tmp_path):
    import json
    from core_agent.core.strike_tips import _bf_form_index, _bf_runner_brief

    cache = {
        "saved_at": __import__("datetime").datetime.now().isoformat(),
        "events": {
            "m1": {
                "course": "Vaal", "raceNumber": 2,
                "runners": [{"name": "Test Horse", "gear": "Hood",
                             "daysSinceRun": 12, "verdict": "Leading contender"}],
            }
        },
    }
    (tmp_path / "betfair_form_last_good.json").write_text(json.dumps(cache))
    idx = _bf_form_index(str(tmp_path))
    assert ("vaal", 2) in idx
    brief = _bf_runner_brief(idx[("vaal", 2)][0])
    assert "Test Horse" in brief and "Hood" in brief and "Leading contender" in brief


def test_snapshot_distances_today_only(tmp_path):
    import json
    from core_agent.core.strike_tips import _snapshot_distances

    snap = {"events": {
        "a": {"course": "Vaal", "raceNumber": 2, "distance_m": 1600, "bf_event_date": "2026-09-17"},
        "b": {"course": "Vaal", "raceNumber": 3, "distance_m": 1200, "bf_event_date": "2026-09-11"},
    }}
    (tmp_path / "market_snapshot_latest.json").write_text(json.dumps(snap))
    out = _snapshot_distances(str(tmp_path), "2026-09-17")
    assert out == {("vaal", 2): 1600}
