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
    """A card that settles the top 4 proves the pick was outside it -> LOSS.

    Nov-2026: the league read "not on the card" as "not top-4" even when the
    card held a single runner. The loss now needs proof — a card carrying
    1st-4th — so this fixture supplies one.
    """
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Second Horse", "position": "2nd", "odds_decimal": 3.0},
        {"name": "Third Horse", "position": "3rd", "odds_decimal": 9.0},
        {"name": "Fourth Horse", "position": "4th", "odds_decimal": 5.0},
    ])])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    settle_open_picks(str(tmp_path))
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is False
    assert row["points"] == 0


def test_settle_open_picks_keeps_a_pick_pending_on_winner_only_evidence(tmp_path):
    """The dated archive records the winner and nothing else.

    "Not the winner" is not evidence of being outside the top 4, so a pick
    that is not the archived winner stays PENDING until a card with positions
    arrives (Nov-2026: Skip The Line, 2nd in Fairview R1, settled a loss).
    """
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Some Other Horse"},
    ])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path))
    assert stats["settled"] == 0
    assert stats["pending"] == 1
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is False
    assert row["points"] == 0


def test_settle_open_picks_keeps_a_pick_pending_on_a_partial_card(tmp_path):
    """A card holding only 1st and 2nd proves nothing about 3rd and 4th.

    The pick is not on the card, so it might be 3rd or 4th — a scoring
    finish. It stays PENDING until the full card lands.
    """
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Second Horse", "position": "2nd", "odds_decimal": 3.0},
    ])])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path))
    assert stats["settled"] == 0
    assert stats["pending"] == 1
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is False


def test_settle_open_picks_scores_a_pick_found_on_a_partial_card(tmp_path):
    """The card names the pick with its position — that IS the proof."""
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "2nd", "odds_decimal": 4.75},
    ])])
    open(os.path.join(tmp_path, "settled_winners.jsonl"), "w").close()
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    assert stats["settled"] == 1
    assert stats["won"] == 1
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is True
    assert row["finish_position"] == 2
    assert row["points"] >= 1


def test_rescore_upgrades_a_pick_settled_without_a_position(tmp_path):
    """Nov-2026: a pick settled a loss from winner-only evidence is upgraded
    once the full card proves it finished in the top 4."""
    from core_agent.skills.league.settlement import rescore_settled_picks

    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(won=False, points=0, settled=True, settled_at="2026-11-04T20:00:00+00:00",
              finish_position=None, winner_name="Some Other Horse", winner_sp=0.0),
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "2nd", "odds_decimal": 4.75},
    ])])

    out = rescore_settled_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    assert out == {"checked": 1, "upgraded": 1}
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is True
    assert row["placed"] is True
    assert row["finish_position"] == 2
    assert row["points"] >= 1
    assert row["winner_name"] == "The Wolf"


def test_rescore_never_downgrades_a_settled_pick(tmp_path):
    """A pick settled with a real position keeps its verdict, win or loss."""
    from core_agent.skills.league.settlement import rescore_settled_picks

    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(won=False, points=0, settled=True, settled_at="2026-11-04T20:00:00+00:00",
              finish_position=5),
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "2nd", "odds_decimal": 4.75},
    ])])

    out = rescore_settled_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    assert out == {"checked": 0, "upgraded": 0}
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is False
    assert row["finish_position"] == 5


def test_settle_open_picks_upgrades_a_past_mis_score(tmp_path):
    """The correction runs as part of every settle pass, so a pick that was
    settled a loss on winner-only evidence is fixed once the card lands."""
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(won=False, points=0, settled=True, settled_at="2026-11-04T20:00:00+00:00",
              finish_position=None),
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
        {"name": "Ragnar The King", "position": "2nd", "odds_decimal": 4.75},
    ])])

    settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["won"] is True
    assert row["finish_position"] == 2
    assert row["points"] >= 1


def test_settle_open_picks_leaves_unknown_races_pending(tmp_path):
    from datetime import date as _date

    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-04", "track": "greyville", "race": "7", "winner": "Ragnar The King"},
    ])
    # Greyville R8 has no confirmed winner on record yet. The pick date is
    # relative so the 7-day expiry window cannot expire the fixture (and
    # fail the test) as the calendar moves.
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17434621", race_number=8, runner_name="The Ghost",
              date=_date.today().isoformat()),
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
    """No result on record -> still PENDING (never a guess).

    The date is relative: the expiry window is 7 days, so a hardcoded
    fixture date made this test expire (and fail) a week after it was
    written (Nov-2026).
    """
    from datetime import date as _date

    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"),
                 [_pick(date=_date.today().isoformat())])
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


# ── full finishing order (per-race /racecard pages) ────────────────────────
# /results truncates at 1st–3rd, so a 4th-place pick was settled as a loss.
# The full card carries 1st–N: 4th must score its floor points.

def _atr_full_race(race_no, runners, course="Carlisle"):
    return {
        "course": course,
        "date": "yesterday",
        "time": "15:35",
        "title": f"{race_no}\n15:35 - NH Flat Race",
        "runners": runners,
    }


def test_atr_full_card_scores_a_fourth_place(tmp_path):
    """The 4th that /results truncates must score, not settle as a loss."""
    _write_atr(tmp_path, [_atr_full_race(7, [
        {"name": "Lady Jetfire", "position": "1st", "odds_decimal": 1.83},
        {"name": "Div Ine Glance", "position": "2nd", "odds_decimal": 15.0},
        {"name": "Who's That Lady", "position": "3rd", "odds_decimal": 21.0},
        {"name": "Afraidso", "position": "4th", "odds_decimal": 17.0},
        {"name": "Betsy Bluesky", "position": "5th", "odds_decimal": 51.0},
    ])])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17500001", course="Carlisle", race_number=7,
              runner_name="Afraidso", pick_odds=16.0, field_size=11),
    ])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is True           # 4th is a scoring finish (top 4)
    assert row["finish_position"] == 4
    assert row["points"] >= 1           # missed points were the bug
    assert stats == {"settled": 1, "won": 1, "pending": 0, "void": 0, "expired": 0}


def test_atr_full_card_fifth_place_is_still_a_loss(tmp_path):
    _write_atr(tmp_path, [_atr_full_race(7, [
        {"name": "Lady Jetfire", "position": "1st", "odds_decimal": 1.83},
        {"name": "Div Ine Glance", "position": "2nd", "odds_decimal": 15.0},
        {"name": "Who's That Lady", "position": "3rd", "odds_decimal": 21.0},
        {"name": "Afraidso", "position": "4th", "odds_decimal": 17.0},
        {"name": "Betsy Bluesky", "position": "5th", "odds_decimal": 51.0},
    ])])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17500002", course="Carlisle", race_number=7,
              runner_name="Betsy Bluesky", pick_odds=50.0, field_size=11),
    ])

    settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is False
    assert row["finish_position"] == 5
    assert row["points"] == 0


def test_atr_non_runner_pick_voids_not_loses(tmp_path):
    """A picked horse recorded as a non-runner refunds (void), never a loss."""
    _write_atr(tmp_path, [_atr_full_race(7, [
        {"name": "Lady Jetfire", "position": "1st", "odds_decimal": 1.83},
        {"name": "Div Ine Glance", "position": "2nd", "odds_decimal": 15.0},
        {"name": "Jackson Court", "position": "", "non_runner": True},
    ])])
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="17500003", course="Carlisle", race_number=7,
              runner_name="Jackson Court", pick_odds=10.0, field_size=11),
    ])

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-05T12:00:00+00:00")
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["void"] is True
    assert row["void_reason"] == "non_runner"
    assert row["won"] is False and row["points"] == 0
    assert stats == {"settled": 0, "won": 0, "pending": 0, "void": 1, "expired": 0}


# ── settlement pass must not die on one row (Nov-2026) ──────────────────────
# The monitor piggyback calls settle_open_picks(now_iso=<aware UTC ISO>).
# The expiry window compared that aware timestamp against a NAIVE pick date,
# raised TypeError on the first pending pick with no result, and aborted the
# whole pass BEFORE the write-back — so the leaderboard never moved and every
# pick stayed "pending" forever. Nothing was logged above debug level.

def test_settle_with_an_aware_now_iso_does_not_crash(tmp_path):
    """An aware now_iso must not abort the pass (the piggyback's shape)."""
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-08", "track": "carlisle", "race": "3", "winner": "Archive Horse"},
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
    ])], ts="2026-11-08T18:00:00")
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        # Settleable pick (has a winner) …
        _pick(race_id="17500010", course="Carlisle", race_number=3,
              date="2026-11-08", runner_name="Archive Horse", pick_odds=5.0),
        # … and one with NO result anywhere (the expiry comparison).
        _pick(race_id="17500011", course="Turffontein", race_number=9,
              date="2026-11-08", runner_name="No Result Horse", pick_odds=7.0),
    ])

    stats = settle_open_picks(
        str(tmp_path), now_iso="2026-11-10T12:00:00+00:00"
    )

    assert stats["settled"] == 1          # the settleable one WAS settled
    rows = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))
    settled = [r for r in rows if r.get("settled")]
    assert len(settled) == 1
    assert settled[0]["runner_name"] == "Archive Horse"
    # The unmatched pick is still pending (it expires after the window).
    assert stats["pending"] == 1


def test_settle_survives_a_broken_pick_row(tmp_path):
    """One poisonous row must not cost the whole pass its settlements."""
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-08", "track": "carlisle", "race": "3", "winner": "Archive Horse"},
    ])
    _write_atr(tmp_path, [_atr_race(7, [
        {"name": "The Wolf", "position": "1st", "odds_decimal": 6.5},
    ])], ts="2026-11-08T18:00:00")
    rows = [
        _pick(race_id="17500020", course="Carlisle", race_number=3,
              date="2026-11-08", runner_name="Archive Horse", pick_odds=5.0),
        # A row whose "date" cannot be parsed at all.
        {"race_id": "17500021", "course": "Carlisle", "race_number": 4,
         "runner_name": "Broken", "settled": False, "won": False, "points": 0},
    ]
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), rows)

    stats = settle_open_picks(str(tmp_path))

    assert stats["settled"] == 1
    out = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))
    assert any(r.get("settled") for r in out)
