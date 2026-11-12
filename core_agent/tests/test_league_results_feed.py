"""Tests for the confirmed-results feed (Raceform -> confirmed_results.jsonl).

Regression guard for Nov-2026: SA meetings were missing from both existing
result sources, so every pick at Greyville/Fairview stayed pending. The feed
supplies full official cards and settlement prefers them.
"""
import json
import os

from core_agent.skills.league.results_feed import (
    append_confirmed_results,
    confirmed_results_as_races,
    load_confirmed_results,
    parse_finish,
    parse_meeting_html,
    parse_odds,
    pending_meetings,
    pending_meetings_otb,
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


# ── the Offtrackbetting fallback (ATR is quiet) ──────────────────────────────

def test_pending_meetings_otb_covers_races_atr_never_published(tmp_path, monkeypatch):
    """A race ATR has no card for is exactly what Offtrackbetting is asked
    for — including the cards Raceform does not cover (Hong Kong)."""
    import core_agent.skills.league.results_feed as rf

    monkeypatch.setattr(rf, "_atr_cards_by_key", lambda: {
        # ATR has this one, with a card good enough to settle the pick:
        # 1st-4th present and the whole field covered.
        ("2026-11-06", "greyville", "1"): [
            {"name": "A", "position": "1st"}, {"name": "B", "position": "2nd"},
            {"name": "C", "position": "3rd"}, {"name": "D", "position": "4th"},
        ] + [{"name": f"X{i}", "position": ""} for i in range(13)],
    })
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(date="2026-11-06", course="Greyville", race_number=1),
        _pick(race_id="h1", date="2026-11-06", course="Happy Valley", race_number=1),
        _pick(race_id="h2", date="2026-11-06", course="Ayr", race_number=4),
    ])

    got = pending_meetings_otb(str(tmp_path), days=3, today=__import__("datetime").date(2026, 11, 7))
    assert ("2026-11-06", "Happy Valley") in got
    assert ("2026-11-06", "Ayr") in got
    assert ("2026-11-06", "Greyville") not in got  # ATR settles this one


def test_pending_meetings_otb_asks_for_a_truncated_atr_card(tmp_path, monkeypatch):
    """ATR holding a race is not ATR answering it (Nov-2026, the USA gap).

    ATR's /results listing truncates every race to the top 1-3, so a
    three-runner card out of twelve proves neither 1st-4th nor the full
    field and settles nothing. Skipping the fallback on the mere presence of
    the key left every USA pick outside the top 3 PENDING for ever while
    Offtrackbetting held the whole card (Horseshoe Indianapolis 7/6/14).
    """
    import core_agent.skills.league.results_feed as rf

    monkeypatch.setattr(rf, "_atr_cards_by_key", lambda: {
        ("2026-11-11", rf._track_key("Churchill Downs (USA)"), "5"): [
            {"name": "A", "position": "1st"},
            {"name": "B", "position": "2nd"},
            {"name": "C", "position": "3rd"},
        ],
    })
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="us1", date="2026-11-11",
              course="Churchill Downs (USA)", race_number=5, field_size=12),
    ])

    got = pending_meetings_otb(
        str(tmp_path), days=3, today=__import__("datetime").date(2026, 11, 12)
    )
    assert ("2026-11-11", "Churchill Downs (USA)") in got


def test_pending_meetings_otb_settles_on_a_complete_atr_card(tmp_path, monkeypatch):
    """Guard against over-fetching: a full-field card must not call OTB."""
    import core_agent.skills.league.results_feed as rf

    full = [{"name": f"H{i}", "position": f"{i}th" if i <= 4 else ""} for i in range(1, 8)]
    monkeypatch.setattr(rf, "_atr_cards_by_key", lambda: {
        ("2026-11-11", rf._track_key("Horseshoe Indianapolis (USA)"), "4"): full,
    })
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(race_id="us2", date="2026-11-11",
              course="Horseshoe Indianapolis (USA)", race_number=4, field_size=7),
    ])

    got = pending_meetings_otb(
        str(tmp_path), days=3, today=__import__("datetime").date(2026, 11, 12)
    )
    assert got == []


def test_pending_meetings_otb_skips_races_with_a_confirmed_card(tmp_path, monkeypatch):
    import core_agent.skills.league.results_feed as rf

    monkeypatch.setattr(rf, "_atr_cards_by_key", lambda: {})
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    append_confirmed_results(str(tmp_path), races)
    _write_jsonl(os.path.join(tmp_path, "league_picks.jsonl"), [
        _pick(date="2026-11-06", course="Greyville", race_number=1),
    ])

    got = pending_meetings_otb(str(tmp_path), days=3, today=__import__("datetime").date(2026, 11, 7))
    assert got == []


def test_confirmed_card_exposes_the_price_the_hud_reads(tmp_path):
    """The HUD prints `runner.odds`; the card stores `odds_decimal`. Without
    the extra field every confirmed card showed "· —" for prices."""
    races = parse_meeting_html(_MEETING_HTML, "Greyville", "2026-11-06")
    append_confirmed_results(str(tmp_path), races)

    out = confirmed_results_as_races(str(tmp_path))
    assert out
    runner = out[0]["runners"][0]
    assert runner["odds"] == "33/1"
    assert runner["odds_decimal"] == 34.0
    assert runner["position"] == "1st"


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
        # The card holds the whole field (4 runners), so it settles where the
        # top 4 ended and a horse without a finish is outside it. The pick's
        # field_size must describe THIS card — a field size the card does not
        # cover would leave the pick pending, which is the point of the rule.
        _pick(runner_number=99, runner_name="Nowhere To Be Seen", field_size=4),
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


# ── a meeting's card fills in race by race (Nov-2026) ───────────────────────
# The backfill skipped a meeting as soon as ANY of its races was confirmed,
# so Kenilworth (fetched at 13:07 for R1-R4) was never fetched again and
# R5-R9 stayed pending forever. Granularity is per RACE, re-fetched on a
# cooldown so an abandoned race cannot hammer Raceform every cycle.

def _write_picks(tmp_path, picks):
    import json as _json
    with open(os.path.join(str(tmp_path), "league_picks.jsonl"), "w") as f:
        for p in picks:
            f.write(_json.dumps(p) + "\n")


def test_pending_meetings_refetches_a_meeting_with_new_pending_races(tmp_path):
    _write_picks(tmp_path, [
        _pick(race_id="1", date="2026-11-10", course="Kenilworth", race_number=5),
    ])
    # R1-R4 are already confirmed for that meeting …
    rows = [
        {"date": "2026-11-10", "course": "Kenilworth", "race_number": str(r),
         "runners": [{"name": "X", "position": 1}]}
        for r in (1, 2, 3, 4)
    ]
    assert append_confirmed_results(str(tmp_path), rows) == 4

    meetings = pending_meetings(str(tmp_path), days=3)
    # … so the meeting still needs a fetch for R5.
    assert ("2026-11-10", "Kenilworth") in meetings


def test_pending_meetings_skips_a_meeting_whose_races_are_all_confirmed(tmp_path):
    _write_picks(tmp_path, [
        _pick(race_id="1", date="2026-11-10", course="Kenilworth", race_number=1),
    ])
    rows = [{"date": "2026-11-10", "course": "Kenilworth", "race_number": "1",
             "runners": [{"name": "X", "position": 1}]}]
    append_confirmed_results(str(tmp_path), rows)

    assert ("2026-11-10", "Kenilworth") not in pending_meetings(str(tmp_path), days=3)


def test_pending_meetings_respects_the_fetch_cooldown(tmp_path):
    _write_picks(tmp_path, [
        _pick(race_id="1", date="2026-11-10", course="Kenilworth", race_number=5),
    ])
    from core_agent.skills.league import results_feed

    results_feed._mark_fetched(str(tmp_path), "2026-11-10", "Kenilworth")
    assert ("2026-11-10", "Kenilworth") not in pending_meetings(
        str(tmp_path), days=3
    )
    # Once the cooldown expires the meeting is fetched again.
    assert ("2026-11-10", "Kenilworth") in pending_meetings(
        str(tmp_path), days=3, cooldown_secs=0
    )


# ── the HUD results tab must not depend on ATR being allowed through ────────
# ATR's browser tier is blocked for long stretches (Nov-2026: the results tab
# went silent mid-meeting). Raceform's cards are server-rendered HTML and
# always work, so the SA meeting is served from them — full finishing order
# plus SP, every race of the day.

def test_off_times_come_from_the_meeting_header():
    html = """
    <div class="winners-glance-list">
      <a class="winners-glance-row" href="#race-1"><span class="wg-race">R1<small>12:37</small></span></a>
      <a class="winners-glance-row" href="#race-2"><span class="wg-race">R2<small>13:07</small></span></a>
    </div>
    """ + _MEETING_HTML
    races = parse_meeting_html(html, "Kenilworth", "2026-11-10")
    assert races[0]["off_time"] == "12:37"


def test_confirmed_results_render_as_atr_shaped_races(tmp_path):
    from core_agent.skills.league.results_feed import confirmed_results_as_races

    append_confirmed_results(str(tmp_path), [{
        "date": "2026-11-10", "course": "Kenilworth", "race_number": "1",
        "off_time": "12:37",
        "runners": [
            {"number": 12, "name": "Peach Cobbler", "position": 1, "odds_decimal": 2.25},
            {"number": 2, "name": "Bursturbubble", "position": 2, "odds_decimal": 6.5},
        ],
    }])

    races = confirmed_results_as_races(str(tmp_path))
    assert len(races) == 1
    r = races[0]
    assert r["title"] == "1 12:37"
    assert r["course"] == "Kenilworth"
    assert r["runners"][0]["position"] == "1st"
    assert r["runners"][1]["position"] == "2nd"


def test_hud_results_merge_prefers_the_fuller_card(tmp_path, monkeypatch):
    """ATR's truncated summary loses to Raceform's full card."""
    from core_agent.routes import monitoring

    monkeypatch.setattr(monitoring, "DATA_DIR", tmp_path)
    append_confirmed_results(str(tmp_path), [{
        "date": "2026-11-10", "course": "Kenilworth (RSA)", "race_number": "1",
        "off_time": "12:37",
        "runners": [
            {"number": 12, "name": "Peach Cobbler", "position": 1, "odds_decimal": 2.25},
            {"number": 2, "name": "Bursturbubble", "position": 2, "odds_decimal": 6.5},
            {"number": 3, "name": "Cape Town Deern", "position": 3, "odds_decimal": 26.0},
        ],
    }])
    atr_blob = {"results": [
        {"course": "Kenilworth (RSA)", "date": "2026-11-10", "time": "12:37",
         "title": "1\n12:37 - Open Maiden", "runners": [
             {"name": "Peach Cobbler", "position": "1st"}]},
    ], "timestamp": "2026-11-10T12:00:00"}

    merged = monitoring._merge_results_with_confirmed(atr_blob)
    races = merged["results"]
    ken = [r for r in races if "kenilworth" in str(r.get("course", "")).lower()]
    assert len(ken) == 1
    assert len(ken[0]["runners"]) == 3      # the full card won
    assert merged["timestamp"] == "2026-11-10T12:00:00"   # blob preserved
