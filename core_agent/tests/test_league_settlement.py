"""Tests for league settlement: JSONL picks settled against confirmed winners.

Regression guard for the Nov-2026 bug where every pick stayed pending forever
because the settle pass read empty Supabase tables instead of the JSONL store.
"""
import json
import os

from core_agent.skills.league.settlement import (
    names_match, load_winner_index, load_winner_details, settle_open_picks,
)


def _write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def _pick(**kw):
    base = {
        "entity_type": "player",
        "entity_id": "uid-1",
        "entity_name": "StriketipsAI",
        "region": "SA",
        "date": "2026-11-04",
        "settled": False,
        "won": False,
        "points": 0,
        "winner_sp": 0.0,
        "pick_odds": 4.75,
        "user_id": "uid-1",
        "race_id": "17434618",
        "course": "Greyville",
        "race_number": 7,
        "off_iso": "2026-11-04T18:40:00+02:00",
        "runner_number": 4,
        "runner_name": "Ragnar The King",
        "field_size": 12,
        "created_at": "2026-11-04T16:01:34+00:00",
        "dedup_key": "17434618|uid-1",
    }
    base.update(kw)
    return base


def test_names_match_exact():
    assert names_match("The Ghost", "the ghost")


def test_names_match_ignores_stopwords_and_parentheticals():
    assert names_match("The Ghost", "Ghost")
    assert names_match("Capability Brown (SAF)", "Capability Brown")


def test_names_match_rejects_different_horses():
    assert not names_match("Ragnar The King", "The Ghost")
    assert not names_match("", "The Ghost")


def test_winner_index_is_keyed_by_date_track_race(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-03", "track": "greyville", "race": "7", "winner": "Old Winner"},
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Ragnar The King"},
    ])
    idx = load_winner_index(str(tmp_path))
    assert idx[("2026-11-04", "greyville", "7")] == "Ragnar The King"
    assert idx[("2026-11-03", "greyville", "7")] == "Old Winner"


def test_settle_open_picks_marks_win_with_points(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Ragnar The King"},
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T06:00:00+00:00")
    assert stats == {"settled": 1, "won": 1, "pending": 0, "void": 0, "expired": 0}

    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is True
    assert row["points"] >= 12  # field size 12 + SP bonus
    assert row["settled_at"] == "2026-11-05T06:00:00+00:00"


def test_settle_open_picks_marks_loss_without_points(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Some Other Horse"},
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    settle_open_picks(str(tmp_path))
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is False
    assert row["points"] == 0


def test_settle_open_picks_leaves_unknown_races_pending(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Ragnar The King"},
    ])
    # Greyville R8 has no confirmed winner on record yet.
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17434621", race_number=8, runner_name="The Ghost"),
    ])

    stats = settle_open_picks(str(tmp_path))
    assert stats["settled"] == 0
    assert stats["pending"] == 1
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is False


def test_settle_open_picks_never_resettles(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Ragnar The King"},
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(won=True, points=17, settled=True, settled_at="2026-11-04T20:00:00+00:00"),
    ])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T06:00:00+00:00")
    assert stats["settled"] == 0
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled_at"] == "2026-11-04T20:00:00+00:00"
    assert row["points"] == 17


def test_settle_open_picks_no_winners_file(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])
    stats = settle_open_picks(str(tmp_path))
    assert stats == {"settled": 0, "won": 0, "pending": 1, "void": 0, "expired": 0}


# ── ATR result cards as a second winner source ──────────────────────────────

def _write_atr(tmp_path, results, ts="2026-11-05T10:05:26+00:00"):
    with open(os.path.join(tmp_path, "atr_results_snapshot.json"), "w") as f:
        json.dump({"timestamp": ts, "results": results}, f)


def _atr_race(race_no, runners, course="Greyville (RSA)"):
    return {
        "course": course,
        "date": "yesterday",
        "time": "18:40",
        "title": f"{race_no}\n18:40 - Handicap (RSA)",
        "runners": runners,
    }


def test_atr_snapshot_settles_a_fourth_place(tmp_path):
    """Top 4 scores: a 4th is a scoring pick, not a loss, and earns the floor."""
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "4th", "odds_decimal": 4.75},
        {"name": "Third Horse", "position": "3rd", "odds_decimal": 9.0},
        {"name": "Second Horse", "position": "2nd", "odds_decimal": 3.0},
    ])])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    assert stats == {"settled": 1, "won": 1, "pending": 0, "void": 0, "expired": 0}
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is True
    assert row["finish_position"] == 4
    assert row["points"] == 2  # 12-runner field * 0.125, floored at 1


def test_atr_snapshot_fifth_place_is_a_loss(tmp_path):
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "5th", "odds_decimal": 4.75},
        {"name": "Third Horse", "position": "3rd", "odds_decimal": 9.0},
        {"name": "Second Horse", "position": "2nd", "odds_decimal": 3.0},
        {"name": "Fourth Horse", "position": "4th", "odds_decimal": 5.0},
    ])])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    assert stats == {"settled": 1, "won": 0, "pending": 0, "void": 0, "expired": 0}
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is False
    assert row["finish_position"] == 5
    assert row["points"] == 0


def test_atr_snapshot_provides_missing_winner(tmp_path):
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "2nd", "odds_decimal": 4.75},
    ])])
    # Nothing in the dated archive for this meeting — ATR fills the gap.
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    # A 2nd-place finish scores (top 4) under the league scoring rules.
    assert stats == {"settled": 1, "won": 1, "pending": 0, "void": 0, "expired": 0}
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is True
    assert row["finish_position"] == 2
    assert row["winner_name"] == "The Wolf"
    assert row["points"] >= 1


def test_atr_snapshot_settles_a_win_with_real_sp(tmp_path):
    _write_atr(tmp_path, [_atr_race(8, [
        {"name": "That's A Gimme", "position": "1st", "odds_decimal": 8.0},
    ])])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17434621", race_number=8, runner_name="Thats A Gimme", pick_odds=8.0),
    ])

    settle_open_picks(str(tmp_path))
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is True
    assert row["winner_sp"] == 8.0
    assert row["points"] >= 12


def test_dated_archive_beats_atr_snapshot(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Archive Horse"},
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "Snapshot Horse", "position": "1st", "odds_decimal": 6.5},
    ])])
    details = load_winner_details(str(tmp_path))
    assert details[("2026-11-04", "greyville", "7")]["winner"] == "Archive Horse"


def test_atr_relative_date_needs_unknown_day_guard(tmp_path):
    # No timestamp and no now_iso -> "yesterday" cannot be resolved, so the
    # snapshot is ignored rather than settling against the wrong day.
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
    ])], ts="")
    assert load_winner_details(str(tmp_path)) == {}
