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


def _fields_page(meeting: str = "Fairview Polytrack") -> str:
    """Compact replica of a Computaform "Best Bets & Perms" Fields page.

    Oct-2026: "Daily Tips" (Tips/TIPPINGSHEET@date.pdf) 404s and PDF discovery
    falls back to this Computaform page, which writes pool ranges as
    "BIPOT (RACES 1 - 6)" with explicit LEG markers — the notation the old
    Tipping-Sheet parser never matched, so no ticket ever carried the TAB
    official picks.
    """
    return (
        "COMPUTAFORM RATINGS\n"
        "BIPOT (RACES 1 - 6)\nR256\n"
        "LEG 1\n6\n"
        "LEG 2\n1\n2\n4\n8\n"
        "LEG 3\n2\n"
        "LEG 4\n1\n3\n5\n6\n"
        "LEG 5\n2\n3\n5\n8\n"
        "LEG 6\n2\n4\n7\n8\n"
        "P/A (RACES 2 - 8)\nR243\n"
        "LEG 1\n1\n2\n4\n"
        "LEG 2\n1\n"
        "LEG 3\n3\n"
        "LEG 4\n3\n5\n6\n"
        "LEG 5\n2\n3\n8\n"
        "LEG 6\n2\n7\n8\n"
        "LEG 7\n1\n4\n5\n"
        "PICK 6 (RACES 3 - 8)\nR1296\n"
        "LEG 1\n2\n"
        "LEG 2\n1\n2\n3\n4\n5\n6\n"
        "LEG 3\n2\n3\n5\n8\n10\n11\n"
        "LEG 4\n2\n3\n4\n7\n8\n9\n"
        "LEG 5\n3\n"
        "LEG 6\n1\n2\n4\n5\n6\n7\n"
        "COMPUTAFORM\n"
        "BEST BETS & PERMS   by Trevor Reid\n"
        f"Tab {meeting}, Friday 16 October 2026\n"
    )


def test_tips_official_picks_fields_page():
    from core_agent.core.strike_tips import _tips_official_picks

    off = _tips_official_picks(_fields_page(), "fairview")
    assert set(off) == {"BI1", "PA", "P6"}
    assert off["BI1"] == {1: [6], 2: [1, 2, 4, 8], 3: [2], 4: [1, 3, 5, 6],
                          5: [2, 3, 5, 8], 6: [2, 4, 7, 8]}
    assert off["PA"] == {2: [1, 2, 4], 3: [1], 4: [3], 5: [3, 5, 6],
                         6: [2, 3, 8], 7: [2, 7, 8], 8: [1, 4, 5]}
    assert off["P6"] == {3: [2], 4: [1, 2, 3, 4, 5, 6],
                         5: [2, 3, 5, 8, 10, 11], 6: [2, 3, 4, 7, 8, 9],
                         7: [3], 8: [1, 2, 4, 5, 6, 7]}


def test_tips_official_picks_scoped_to_meeting():
    from core_agent.core.strike_tips import _tips_official_picks

    # A Fairview page must not leak its picks onto a Greyville play.
    assert _tips_official_picks(_fields_page("Fairview Polytrack"), "greyville") == {}
    # Sponsored meeting names still match the bare track key.
    grey = _tips_official_picks(
        _fields_page("Hollywoodbets Greyville Polytrack"), "greyville")
    assert grey["BI1"][1] == [6]


def test_tips_pool_starts_fields_page():
    from core_agent.core.strike_tips import _tips_pool_starts

    assert _tips_pool_starts(_fields_page(), "fairview") == {
        "BI1": 1, "PA": 2, "P6": 3}


def test_tips_official_picks_legacy_tipping_sheet():
    from core_agent.core.strike_tips import _tips_official_picks

    # Multi-meeting Tipping Sheet notation ("Bipot (2-7)" + comma lines)
    # must keep working alongside the Fields-page format.
    text = ("DURBANVILLE\nBipot (2-7)\nR480\n"
            "1, 7, 9, 10\n1, 9\n3\n2, 8\n5\n6, 11\n"
            "INTERNATIONAL\n")
    off = _tips_official_picks(text, "durbanville")
    assert off["BI1"] == {2: [1, 7, 9, 10], 3: [1, 9], 4: [3],
                          5: [2, 8], 6: [5], 7: [6, 11]}
