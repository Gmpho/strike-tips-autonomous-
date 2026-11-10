"""Tests for the confirmed-results feed (Raceform -> confirmed_results.jsonl).

Regression guard for Nov-2026: SA meetings were missing from both existing
result sources, so every pick at Greyville/Fairview stayed pending. The feed
supplies full official cards and settlement prefers them.
"""
import json
import os

from core_agent.skills.league.results_feed import (
    append_confirmed_results,
    load_confirmed_results,
    parse_finish,
    parse_meeting_html,
    parse_odds,
    pending_meetings,
)
from core_agent.skills.league.settlement import load_winner_details, settle_open_picks

_MEETING_HTML = """
<html><body>
<div id="race-1" class="racecard-body">
  <h3>Race 1 Maiden Plate (F&amp;M)</h3>
  <table>
    <thead><tr><th>AR</th><th>Finish</th><th>LBH</th><th>No</th><th>Horse</th>
    <th>Draw</th><th>Mass</th><th>Jockey</th><th>Odds</th></tr></thead>
    <tbody>
      <tr><td>70</td><td>1</td><td>0.00</td><td>13</td>
        <td><a href="/horses/220289">Eagle Has Landed</a> 3 b f</td>
        <td>(13)</td><td>59.0</td><td>C Habib</td><td>33/1</td></tr>
      <tr><td>69</td><td>2</td><td>0.75</td><td>10</td>
        <td><a href="/horses/220284">Willow Valli</a> 4 b f</td>
        <td>(10)</td><td>60.0</td><td>K de Melo</td><td>17/2</td></tr>
      <tr><td>58</td><td>3</td><td>2.25</td><td>4</td>
        <td><a href="/horses/221431">Ferrari Flair</a> 5 b g</td>
        <td>(4)</td><td>60.0</td><td>S Moodley</td><td>9/20</td></tr>
      <tr><td>0</td><td>PU</td><td>0.00</td><td>7</td>
        <td><a href="/horses/219999">Pulled Up</a> 6 b g</td>
        <td>(7)</td><td>60.0</td><td>X Ndlovu</td><td></td></tr>
    </tbody>
  </table>
</div>
<div id="race-2" class="racecard-body">
  <h3>Race 2 Abandoned</h3>
  <p>No result table.</p>
</div>
</body></html>
"""


def _pick(**kw):
    base = {
        "entity_type": "player", "entity_id": "uid-1", "entity_name": "StriketipsAI",
        "region": "SA", "date": "2026-11-06", "settled": False, "won": False,
        "points": 0, "winner_sp": 0.0, "pick_odds": 8.5, "user_id": "uid-1",
        "race_id": "17440001", "course": "Greyville", "race_number": 1,
        "runner_number": 10, "runner_name": "Willow Valli", "field_size": 17,
        "created_at": "2026-11-06T08:00:00+00:00", "dedup_key": "17440001|uid-1",
    }
    base.update(kw)
    return base


def _write_jsonl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def _read_jsonl(path):
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


# ── parsing ─────────────────────────────────────────────────────────────────

def test_parse_odds_handles_fractional_evens_and_blanks():
    assert parse_odds("33/1") == 34.0
    assert parse_odds("17/2") == 9.5
    assert parse_odds("9/20") == 1.45
    assert parse_odds("EVS") == 2.0
    assert parse_odds("R2.50") == 2.5
    assert parse_odds("") is None
    assert parse_odds("SP") is None


def test_parse_finish_rejects_non_finishers():
    assert parse_finish("1") == 1
    assert parse_finish("2nd") == 2
    assert parse_finish("PU") is None
    assert parse_finish("0") is None
    assert parse_finish("") is None


def test_parse_meeting_html_extracts_full_card():
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    assert len(races) == 2  # real race + the abandoned race, recorded as void
    race = races[0]
    assert race["race_number"] == "1"
    assert race["race_number"] == "1"
    assert race["date"] == "2026-11-06"
    assert race["course"] == "Greyville"

    runners = {r["name"]: r for r in race["runners"]}
    assert runners["Eagle Has Landed"]["position"] == 1
    assert runners["Eagle Has Landed"]["number"] == 13
    assert runners["Eagle Has Landed"]["odds_decimal"] == 34.0
    # Link text wins over the "age colour sex" suffix in the cell.
    assert "Willow Valli" in runners
    assert runners["Willow Valli"]["position"] == 2
    assert runners["Pulled Up"]["position"] is None
    assert runners["Pulled Up"]["odds_decimal"] is None


# ── storage ─────────────────────────────────────────────────────────────────

def test_append_is_idempotent_and_latest_write_wins(tmp_path):
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    assert append_confirmed_results(str(tmp_path), races) == 2
    assert append_confirmed_results(str(tmp_path), races) == 2

    stored = load_confirmed_results(str(tmp_path))
    assert len(stored) == 2  # real race + void race, replaced not duplicated

    corrected = json.loads(json.dumps(races))
    corrected[0]["runners"][0]["name"] = "Corrected Winner"
    append_confirmed_results(str(tmp_path), corrected)
    stored = load_confirmed_results(str(tmp_path))
    assert len(stored) == 2
    assert stored[0]["runners"][0]["name"] == "Corrected Winner"


def test_pending_meetings_only_covers_sa_raceform_tracks(tmp_path):
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(date="2026-11-06", course="Greyville"),
        _pick(date="2026-11-06", course="Fairview", race_id="2"),
        _pick(date="2026-11-06", course="Newcastle", race_id="3"),   # not SA
        _pick(date="2026-11-06", course="Clairwood", race_id="4"),   # no cards
        _pick(date="2026-10-01", course="Greyville", race_id="5"),   # too old
        _pick(date="2026-11-06", course="Vaal", race_id="6", settled=True),
    ])
    got = pending_meetings(str(tmp_path), days=3, today=__import__("datetime").date(2026, 11, 7))
    assert got == [("2026-11-06", "Fairview"), ("2026-11-06", "Greyville")]


# ── settlement integration ──────────────────────────────────────────────────

def test_confirmed_card_beats_winner_only_archive(tmp_path):
    # The archive thinks a different horse won and knows no positions.
    _write_jsonl(os.path.join(tmp_path, "settled_winners.jsonl"), [
        {"date": "2026-11-06", "track": "greyville", "race": "1", "winner": "Someone Else"},
    ])
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    append_confirmed_results(str(tmp_path), races)
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [_pick()])

    details = load_winner_details(str(tmp_path))
    assert details[("2026-11-06", "greyville", "1")]["winner"] == "Eagle Has Landed"

    stats = settle_open_picks(str(tmp_path), now_iso="2026-11-07T04:00:00+00:00")
    assert stats == {"settled": 1, "won": 1, "pending": 0, "void": 0, "expired": 0}

    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["finish_position"] == 2
    assert row["won"] is True           # top-3 counts as placed
    # Half of a 17-runner field is 8.5; round() is half-to-even, so 8.
    assert row["points"] == 8
    assert row["winner_name"] == "Eagle Has Landed"


def test_confirmed_card_settles_unplaced_pick_as_loss(tmp_path):
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    races[0]["runners"].append({
        "number": 99, "name": "Nowhere To Be Seen",
        "position": None, "odds_decimal": 50.0,
    })
    append_confirmed_results(str(tmp_path), races)
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(runner_number=99, runner_name="Nowhere To Be Seen"),
    ])

    settle_open_picks(str(tmp_path))
    row = _read_jsonl(os.path.join(tmp_path, "league_picks.jsonl"))[0]
    assert row["settled"] is True
    assert row["won"] is False
    assert row["points"] == 0


# ── Raceform serves the LATEST meeting, not the date in the URL ─────────────
# Asking for kenilworth/2026-11-04 returns TODAY's card. Stamping that card
# with the requested date would settle a past pick against another day's
# runners — a would-be winner scored as a loss. The displayed meeting date
# is now checked before the card is accepted.

_HEAD = """
<div class="winners-glance-head">
  <h2>{heading}</h2>
  <span>{count} races &middot; Going: g </span>
</div>
"""


def _html_with_head(heading):
    return _HEAD.format(heading=heading, count=1) + _MEETING_HTML


def test_meeting_date_is_read_from_the_page_head():
    from core_agent.skills.league.results_feed import meeting_date_from_html

    assert meeting_date_from_html(
        _html_with_head("Tuesday 10 November 2026")
    ) == "2026-11-10"
    assert meeting_date_from_html(
        _html_with_head("Sunday 8 November 2026")
    ) == "2026-11-08"
    assert meeting_date_from_html("<html><body>nothing</body></html>") is None


def test_fetch_meeting_refuses_a_card_from_another_day(monkeypatch):
    """A page showing a different meeting must yield NO results."""
    from core_agent.skills.league import results_feed

    class _Resp:
        text = _html_with_head("Tuesday 10 November 2026")

        def raise_for_status(self):
            return None

    monkeypatch.setattr(
        "httpx.get", lambda *a, **k: _Resp()
    )
    races = results_feed.fetch_meeting("Kenilworth", "2026-11-04")
    assert races == []


def test_fetch_meeting_accepts_the_matching_day(monkeypatch):
    from core_agent.skills.league import results_feed

    class _Resp:
        text = _html_with_head("Sunday 8 November 2026")

        def raise_for_status(self):
            return None

    monkeypatch.setattr("httpx.get", lambda *a, **k: _Resp())
    races = results_feed.fetch_meeting("Turffontein", "2026-11-08")
    assert len(races) == 2          # race 1 + the void race 2
    assert races[0]["date"] == "2026-11-08"
    assert races[1]["void"] is True
