"""League picks must be settled against the race they were placed in.

Nov-2026: the odds feed numbered the Horseshoe Indianapolis meeting
differently from ATR — the same 18:30 race was "R4" in the market snapshot
and "R1" in ATR's own card. A league pick records the feed's number, so
"Apotheon" (who won ATR's R1) was settled a LOSS because his pick said R3,
and "Four Star General" (2nd in R2) sat PENDING against a card that could
never place him.

The off time is the one identifier every feed agrees on, so it decides which
race a pick belongs to — but only when the evidence agrees with it. A horse
that is on neither card is never lost on a card that may belong to another
race.
"""
import json
import os

from core_agent.skills.league.settlement import (
    _utc_hhmm,
    load_winner_details_by_time,
    repair_misnumbered_picks,
    settle_open_picks,
)
from core_agent.skills.league.results_feed import _off_time_utc


def _write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _write_atr(tmp_path, results, ts="2026-11-11T23:00:00+00:00"):
    with open(os.path.join(tmp_path, "atr_results_snapshot.json"), "w") as f:
        json.dump({"timestamp": ts, "results": results}, f)


def _atr_race(race_no, hhmm, runners, course="Horseshoe Indianapolis (USA)"):
    """One ATR card. ATR states card times in UTC for every region."""
    return {
        "course": course,
        "date": "2026-11-11",
        "title": f"{race_no}\n{hhmm} - Race {race_no} - Claiming",
        "runners": runners,
    }


def _pick(**kw):
    base = {
        "entity_type": "player", "entity_id": "uid-1", "entity_name": "Mpho",
        "region": "USA", "date": "2026-11-11", "settled": False, "won": False,
        "points": 0, "winner_sp": 0.0, "pick_odds": 4.33, "user_id": "uid-1",
        "race_id": "17468708", "course": "Horseshoe Indianapolis",
        "race_number": 3, "off_iso": "2026-11-11T18:30:00+00:00",
        "runner_number": 2, "runner_name": "Apotheon", "field_size": 7,
        "created_at": "2026-11-11T18:08:57+00:00", "dedup_key": "17468708|uid-1",
    }
    base.update(kw)
    return base


# ── off-time normalisation ──────────────────────────────────────────────────

def test_utc_hhmm_converts_a_local_off_time():
    """A SA pick's off time is written in SAST; ATR's titles are UTC."""
    assert _utc_hhmm("2026-11-12T12:15:00+02:00") == "10:15"
    assert _utc_hhmm("2026-11-11T18:30:00+00:00") == "18:30"
    assert _utc_hhmm("") == ""
    assert _utc_hhmm("not a time") == ""


def test_off_time_utc_states_the_frame_of_each_source():
    """Raceform writes SA wall clock; Offtrackbetting writes UTC already."""
    assert _off_time_utc("12:15", "Greyville", "raceform") == "10:15"
    assert _off_time_utc("18:30", "Horseshoe Indianapolis", "otb") == "18:30"
    assert _off_time_utc("", "Greyville", "raceform") == ""
    assert _off_time_utc("nope", "Greyville", "raceform") == ""


# ── settlement resolves the race by off time ────────────────────────────────

def test_pick_settles_against_the_race_its_off_time_proves(tmp_path):
    """The stored race number points at another race; the off time does not."""
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Apotheon", "position": "1st", "odds_decimal": 4.33},
            {"name": "Family Crest", "position": "2nd", "odds_decimal": 6.0},
        ]),
        _atr_race(3, "19:36", [
            {"name": "Candle's Legacy", "position": "1st", "odds_decimal": 3.0},
            {"name": "British Empress", "position": "2nd", "odds_decimal": 5.0},
            {"name": "Cloudy Lass", "position": "3rd", "odds_decimal": 7.0},
        ]),
    ])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    assert stats["settled"] == 1
    assert stats["won"] == 1
    rows = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))
    assert rows[0]["won"] is True
    assert rows[0]["finish_position"] == 1
    assert rows[0]["race_number"] == 1


def test_horse_on_neither_card_stays_pending(tmp_path):
    """No proof, no verdict: a card from another race cannot settle a loss."""
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Someone Else", "position": "1st", "odds_decimal": 4.33},
            {"name": "Other Horse", "position": "2nd", "odds_decimal": 6.0},
            {"name": "Third Horse", "position": "3rd", "odds_decimal": 7.0},
            {"name": "Fourth Horse", "position": "4th", "odds_decimal": 8.0},
        ]),
        _atr_race(3, "19:36", [
            {"name": "Candle's Legacy", "position": "1st", "odds_decimal": 3.0},
            {"name": "British Empress", "position": "2nd", "odds_decimal": 5.0},
            {"name": "Cloudy Lass", "position": "3rd", "odds_decimal": 7.0},
        ]),
    ])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    assert stats["settled"] == 0
    rows = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))
    assert rows[0]["settled"] is False


# ── the repair pass ─────────────────────────────────────────────────────────

def test_repair_renumbers_the_pick_and_keeps_the_original(tmp_path):
    """ATR proves R1 for the pick's off time; the feed said R3."""
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Apotheon", "position": "1st", "odds_decimal": 4.33},
        ]),
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = repair_misnumbered_picks(
        str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    assert stats["repaired"] == 1
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["race_number"] == 1
    assert row["race_number_corrected"]["from"] == "3"
    assert row["race_number_corrected"]["to"] == 1


def test_repair_leaves_a_pick_alone_without_proof(tmp_path):
    """ATR does not list the horse for that instant: no change, no guess."""
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Someone Else", "position": "1st", "odds_decimal": 4.33},
        ]),
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = repair_misnumbered_picks(
        str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    assert stats["repaired"] == 0
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["race_number"] == 3
    assert "race_number_corrected" not in row


def test_repair_never_touches_a_settled_verdict(tmp_path):
    """A pick settled with a position has spoken; its number stays put."""
    settled = _pick(settled=True, won=True, finish_position=1, points=40)
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Apotheon", "position": "1st", "odds_decimal": 4.33},
        ]),
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [settled])

    stats = repair_misnumbered_picks(
        str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    assert stats["repaired"] == 0
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["race_number"] == 3


def test_a_settled_false_loss_is_upgraded_after_the_repair(tmp_path):
    """The Nov-2026 case end to end: a winner booked as a loss."""
    false_loss = _pick(settled=True, won=False, placed=False, points=0,
                       finish_position=None, settled_at="2026-11-11T19:52:28+00:00")
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Apotheon", "position": "1st", "odds_decimal": 4.33},
            {"name": "Family Crest", "position": "2nd", "odds_decimal": 6.0},
        ]),
    ])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [false_loss])

    settle_open_picks(str(tmp_path), now_iso="2026-11-11T20:00:00+00:00")

    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["race_number"] == 1
    assert row["won"] is True
    assert row["finish_position"] == 1
    assert row["points"] > 0


# ── the time index ──────────────────────────────────────────────────────────

def test_evidence_is_indexed_by_utc_off_time(tmp_path):
    """ATR's title time is UTC, so it lines up with a pick's UTC off time."""
    _write_atr(tmp_path, [
        _atr_race(1, "18:30", [
            {"name": "Apotheon", "position": "1st", "odds_decimal": 4.33},
        ]),
    ])
    index = load_winner_details_by_time(str(tmp_path))
    assert ("2026-11-11", "horseshoe indianapolis", "18:30") in index
    assert index[("2026-11-11", "horseshoe indianapolis", "18:30")]["race_number"] == "1"


def test_a_confirmed_card_is_indexed_by_its_utc_off_time(tmp_path):
    """Cards state their UTC time, so they can be matched by instant too."""
    _write_jsonl(os.path.join(tmp_path, "confirmed_results.jsonl"), [{
        "date": "2026-11-11",
        "course": "Horseshoe Indianapolis",
        "race_number": "2",
        "off_time": "19:05",
        "off_time_utc": "19:05",
        "runners": [
            {"name": "Infinite Speed", "position": 1, "odds_decimal": 2.38},
            {"name": "Four Star General", "position": 2, "odds_decimal": 5.5},
        ],
        "source": "otb",
    }])
    index = load_winner_details_by_time(str(tmp_path))
    entry = index[("2026-11-11", "horseshoe indianapolis", "19:05")]
    assert entry["race_number"] == "2"
    assert entry["winner"] == "Infinite Speed"
