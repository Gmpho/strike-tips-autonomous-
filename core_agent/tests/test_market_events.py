"""The canonical market event store.

A price move used to be expressed four ways by four derivations (a Logs
alert, a Market Movers card, a Live Ops line, a Telegram row) so the
surfaces disagreed and none of them knew the user's own pick was involved.

These tests pin the rules that make one record trustworthy: one move is one
record, a market *opening* is not a move, a book switch is not a move, one
busy race cannot flood the feed, and a fallback source can never pretend to
be fresher than it is.
"""

import json
import os
from datetime import datetime, timedelta

import pytest

from core_agent.core import market_events as me


# ── fixtures ────────────────────────────────────────────────────────────────

def _snapshot(entries, ts="2026-11-13T10:00:00"):
    """A minimal market snapshot shaped like the real one.

    ``entries`` is a list of (course, race_number, horse, odds[, book]).
    """
    events = {}
    for idx, entry in enumerate(entries):
        course, race_number, horse, odds = entry[:4]
        book = entry[4] if len(entry) > 4 else None
        key = f"{course[:3].lower()}{race_number}00{idx}"
        runner = {"name": horse, "number": str(idx + 1), "odds": odds}
        if book:
            runner["book"] = book
        events[key] = {
            "id": key,
            "course": course,
            "raceNumber": race_number,
            "t": "14:15",
            "bf_off_time": "16:15",
            "runners": [runner],
        }
    return {"timestamp": ts, "events": events}


@pytest.fixture
def store(tmp_path):
    """Paths for an isolated store + baseline."""
    return {
        "events_path": tmp_path / "market_events.jsonl",
        "baseline_path": tmp_path / "market_price_baseline.json",
        "picks_dir": str(tmp_path),
    }


def _diff(store, snapshot, now=None, picks=None):
    return me.diff_snapshot(
        snapshot,
        picks=picks if picks is not None else [],
        now=now or datetime(2026, 11, 13, 10, 0, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )


# ── one move, one record ────────────────────────────────────────────────────

def test_a_real_move_is_recorded_once(store):
    """11.0 → 6.5 across two snapshots is one record with both prices."""
    me.diff_snapshot(
        _snapshot([("Greyville", 1, "Bright Comet", 11.0)]),
        picks=[],
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    written = _diff(
        store,
        _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                  ts="2026-11-13T10:05:00"),
        now=datetime(2026, 11, 13, 10, 5),
    )

    assert len(written) == 1
    event = written[0]
    assert event["kind"] == me.KIND_PRICE_MOVE
    assert event["prev"] == 11.0
    assert event["price"] == 6.5
    assert event["move_pct"] == pytest.approx(40.9, abs=0.05)
    assert event["direction"] == "shortened"
    assert event["severity"] == "steamer"
    assert event["source"] == "snapshot"
    assert event["book"] == "betway"

    stored = me.read_events(path=store["events_path"])
    assert len(stored) == 1


def test_the_same_transition_cannot_be_stored_twice(store):
    """Two sources seeing 3.5 -> 2.87 must not make two records."""
    event = {
        "id": me.move_id("Greyville", 1, "Bright Comet", 3.5, 2.87),
        "ts": "2026-11-13T10:00:00",
        "kind": me.KIND_PRICE_MOVE,
    }
    assert me.append_events([event], path=store["events_path"]) == [event]
    assert me.append_events([event], path=store["events_path"]) == []
    assert len(me.read_events(path=store["events_path"])) == 1


def test_a_drift_is_directional_and_not_a_steamer(store):
    _diff(store, _snapshot([("Vaal", 5, "King Lee", 3.0)]))
    written = _diff(store, _snapshot([("Vaal", 5, "King Lee", 4.2)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5))
    assert len(written) == 1
    assert written[0]["move_pct"] < 0
    assert written[0]["direction"] == "drifted"
    assert written[0]["severity"] == "drifter"


# ── a market opening is not a move ──────────────────────────────────────────

@pytest.mark.parametrize("placeholder", ["SP", 0, 1, None, "n/a", ""])
def test_placeholder_to_real_price_is_not_a_move(store, placeholder):
    """Bahrain's whole card is SP until the off — that is an opening, not news."""
    me.diff_snapshot(
        _snapshot([("Bahrain", 1, "Royal Champion", placeholder)]),
        picks=[],
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    written = _diff(store, _snapshot([("Bahrain", 1, "Royal Champion", 6.0)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5))
    assert written == []


def test_real_to_placeholder_is_not_a_move(store):
    """A runner going SP (non-runner, feed gap) is a withdrawal, not drift."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 3.5)]))
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", "SP")],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5))
    assert written == []


def test_a_change_below_threshold_is_not_a_move(store):
    """2.00 -> 2.02 is noise; it must not become a Movers card."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 2.00)]))
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 2.02)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5))
    assert written == []


# ── same-book rule ──────────────────────────────────────────────────────────

def test_a_book_switch_is_not_a_move(store):
    """Betway 3.5 -> ATR 2.5 is two different opinions, not a price move."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 3.5, "betway")]))
    written = _diff(
        store,
        _snapshot([("Greyville", 1, "Bright Comet", 2.5, "atr")],
                  ts="2026-11-13T10:05:00"),
        now=datetime(2026, 11, 13, 10, 5),
    )
    assert written == []


def test_moves_are_tracked_per_book_independently(store):
    """Each book keeps its own baseline, so both can report their own move."""
    _diff(store, _snapshot([
        ("Greyville", 1, "Bright Comet", 3.5, "betway"),
        ("Greyville", 1, "Bright Comet", 3.4, "atr"),
    ]))
    written = _diff(
        store,
        _snapshot([
            ("Greyville", 1, "Bright Comet", 2.8, "betway"),
            ("Greyville", 1, "Bright Comet", 2.7, "atr"),
        ], ts="2026-11-13T10:05:00"),
        now=datetime(2026, 11, 13, 10, 5),
    )
    books = sorted(e["book"] for e in written)
    assert books == ["atr", "betway"]


# ── debounce ────────────────────────────────────────────────────────────────

def test_a_runner_is_quiet_for_the_cooldown(store):
    """A runner that just moved cannot move again inside the window."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 11.0)]))
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                           ts="2026-11-13T10:05:00"),
          now=datetime(2026, 11, 13, 10, 5))
    # 4 minutes later: still inside the 10-minute window.
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 5.0)],
                                     ts="2026-11-13T10:09:00"),
                    now=datetime(2026, 11, 13, 10, 9))
    assert written == []


def test_a_runner_speaks_again_after_the_cooldown(store):
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 11.0)]))
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                           ts="2026-11-13T10:05:00"),
          now=datetime(2026, 11, 13, 10, 5))
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 4.0)],
                                     ts="2026-11-13T10:20:00"),
                    now=datetime(2026, 11, 13, 10, 20))
    assert len(written) == 1


def test_one_busy_race_is_capped(store):
    """Six runners all moving in one race collapse to the biggest moves."""
    names = [f"Horse {i}" for i in range(6)]
    me.diff_snapshot(
        _snapshot([("Greyville", 1, n, 10.0) for n in names]),
        picks=[],
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    # Every runner shortens, by different amounts.
    written = _diff(
        store,
        _snapshot([("Greyville", 1, n, 10.0 - (i + 1) * 0.5)
                   for i, n in enumerate(names)],
                  ts="2026-11-13T10:05:00"),
        now=datetime(2026, 11, 13, 10, 5),
    )
    assert len(written) == me.MAX_EVENTS_PER_RACE
    # ...and they are the biggest, not an arbitrary three.
    assert [e["runner"]["name"] for e in written] == ["Horse 5", "Horse 4", "Horse 3"]


def test_a_runner_produces_one_event_per_poll(store):
    """Same runner, same poll, two snapshots — still one event."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 10.0)]))
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 2.0)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5))
    assert len(written) == 1


# ── the user's pick ─────────────────────────────────────────────────────────

def test_the_event_knows_the_users_pick(store, tmp_path):
    """A move on a runner the user holds must be marked as theirs."""
    (tmp_path / "league_picks.jsonl").write_text(json.dumps({
        "date": "2026-11-13",
        "course": "Greyville (RSA)",
        "race_number": 1,
        "runner_name": "Bright Comet",
        "pick_odds": 11.0,
        "handle": "StriketipsAI",
    }) + "\n")

    picks = me.load_pick_index(data_dir=str(tmp_path), date="2026-11-13")
    assert len(picks) == 1

    me.diff_snapshot(
        _snapshot([("Greyville", 1, "Bright Comet", 11.0)]),
        picks=picks,
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5), picks=picks)
    assert written[0]["is_user_pick"] is True
    assert written[0]["pick"]["handle"] == "StriketipsAI"


def test_a_move_we_hold_no_pick_on_is_not_marked(store):
    me.diff_snapshot(
        _snapshot([("Greyville", 1, "Bright Comet", 11.0)]),
        picks=[],
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    written = _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                                     ts="2026-11-13T10:05:00"),
                    now=datetime(2026, 11, 13, 10, 5), picks=[])
    assert "is_user_pick" not in written[0]


# ── ATR is a labelled fallback ──────────────────────────────────────────────

def test_atr_events_carry_their_source_and_age():
    """A 45-minute-old ATR row must say so rather than pose as live."""
    now = datetime(2026, 11, 13, 10, 0)
    fetched = now - timedelta(minutes=45)
    events = me.from_atr(
        [{"horse": "King Lee", "course": "Churchill Downs", "time": "14:35",
          "current_odds": 2.87, "first_show": 3.5, "movement": "+18%"}],
        fetched_at=fetched.isoformat(),
        now=now,
    )
    assert len(events) == 1
    assert events[0]["source"] == "atr"
    assert events[0]["age_secs"] == 45 * 60
    assert events[0]["move_pct"] == pytest.approx(18.0, abs=0.05)


def test_atr_cannot_outrank_a_course_we_scrape(store):
    """If we observed Greyville ourselves, ATR's Greyville rows are dropped."""
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 11.0)]))
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                           ts="2026-11-13T10:05:00"),
          now=datetime(2026, 11, 13, 10, 5))

    atr = {
        "timestamp": "2026-11-13T09:30:00",
        "movers": [
            {"horse": "Bright Comet", "course": "Greyville", "time": "14:37",
             "current_odds": 6.0, "first_show": 11.0, "movement": "+45%"},
            {"horse": "King Lee", "course": "Churchill Downs", "time": "14:35",
             "current_odds": 2.87, "first_show": 3.5, "movement": "+18%"},
        ],
    }
    rows = me.movers_for_hud(atr_blob=atr, events_path=store["events_path"])
    courses = [r["course"] for r in rows]
    assert "Churchill Downs" in courses          # fallback fills the gap
    assert courses.count("Greyville") == 1       # ours, not ATR's duplicate
    greyville = next(r for r in rows if r["course"] == "Greyville")
    assert greyville["source"] == "snapshot"


def test_every_movers_row_states_its_source_and_age(store):
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 11.0)]))
    _diff(store, _snapshot([("Greyville", 1, "Bright Comet", 6.5)],
                           ts="2026-11-13T10:05:00"),
          now=datetime(2026, 11, 13, 10, 5))
    rows = me.movers_for_hud(events_path=store["events_path"])
    assert rows
    for row in rows:
        assert row["source"] in ("snapshot", "atr")
        assert "age_secs" in row


# ── alerts share the same store ─────────────────────────────────────────────

def test_an_alert_is_normalised_into_the_store(store):
    msg = {
        "alert_id": "global_odds_drop",
        "type": "odds_drop",
        "course": "Vaal",
        "horse": "King Lee",
        "odds": "2.87",
        "race": "5",
        "timestamp": "2026-11-13T10:00:00",
        "journey": {"open": 3.5, "open_at": "2026-11-13T04:55"},
    }
    written = me.record_alert(msg, events_path=store["events_path"])
    assert len(written) == 1
    event = written[0]
    assert event["kind"] == me.KIND_ODDS_DROP
    assert event["source"] == "alert_engine"
    assert event["prev"] == 3.5
    assert event["price"] == 2.87

    alerts = me.alerts_for_hud(events_path=store["events_path"])
    assert len(alerts) == 1
    # The HUD's existing shape still holds.
    assert alerts[0]["type"] == "odds_drop"
    assert alerts[0]["horse"] == "King Lee"
    assert alerts[0]["odds"] == 2.87
    assert alerts[0]["race"] == "5"


def test_a_message_without_a_real_price_is_not_recorded(store):
    """An SP alert is not an alert on a price we can quote."""
    for odds in ("SP", 0, None, "n/a"):
        assert me.record_alert(
            {"type": "odds_drop", "course": "Vaal", "horse": "King Lee",
             "odds": odds, "race": "5", "timestamp": "2026-11-13T10:00:00"},
            events_path=store["events_path"],
        ) == []


def test_a_non_odds_alert_type_is_not_a_market_event(store):
    assert me.record_alert(
        {"type": "value_bet", "course": "Vaal", "horse": "King Lee",
         "odds": 3.0, "race": "5", "timestamp": "2026-11-13T10:00:00"},
        events_path=store["events_path"],
    ) == []


# ── retention + robustness ──────────────────────────────────────────────────

def test_old_events_are_pruned(store):
    old = {
        "id": "pm_old",
        "ts": (datetime.now() - timedelta(hours=me.MAX_AGE_HOURS + 2)).isoformat(),
        "kind": me.KIND_PRICE_MOVE,
    }
    new = {"id": "pm_new", "ts": datetime.now().isoformat(),
           "kind": me.KIND_PRICE_MOVE}
    me.append_events([old], path=store["events_path"])
    me.append_events([new], path=store["events_path"])
    stored = {e["id"] for e in me.read_events(path=store["events_path"])}
    assert stored == {"pm_new"}


def test_a_corrupt_line_does_not_break_reading(store):
    store["events_path"].write_text(
        '{"id":"ok","ts":"%s","kind":"price_move"}\n'
        'not json at all\n'
        '\n'
        % datetime.now().isoformat()
    )
    rows = me.read_events(path=store["events_path"])
    assert [r["id"] for r in rows] == ["ok"]


def test_a_bad_snapshot_is_survivable(store):
    assert _diff(store, {}) == []
    assert _diff(store, {"events": "nonsense"}) == []
    assert _diff(store, {"events": {"x": None}}) == []


def test_finished_races_are_ignored(store):
    snap = _snapshot([("Greyville", 1, "Bright Comet", 11.0)])
    me.diff_snapshot(snap, picks=[], now=datetime(2026, 11, 13, 10, 0),
                     baseline_path=store["baseline_path"],
                     events_path=store["events_path"])
    snap2 = _snapshot([("Greyville", 1, "Bright Comet", 2.0)],
                      ts="2026-11-13T10:05:00")
    for event in snap2["events"].values():
        event["isFinished"] = True
    assert _diff(store, snap2, now=datetime(2026, 11, 13, 10, 5)) == []


def test_non_runners_are_ignored(store):
    snap = _snapshot([("Greyville", 1, "Bright Comet", 11.0)])
    me.diff_snapshot(snap, picks=[], now=datetime(2026, 11, 13, 10, 0),
                     baseline_path=store["baseline_path"],
                     events_path=store["events_path"])
    snap2 = _snapshot([("Greyville", 1, "Bright Comet", 2.0)],
                      ts="2026-11-13T10:05:00")
    for event in snap2["events"].values():
        event["runners"][0]["non_runner"] = True
    assert _diff(store, snap2, now=datetime(2026, 11, 13, 10, 5)) == []


def test_a_new_day_does_not_compare_against_yesterdays_price(store):
    """Same course, same race number, same horse name — different race."""
    me.diff_snapshot(
        _snapshot([("Greyville", 1, "Bright Comet", 11.0)],
                  ts="2026-11-12T10:00:00"),
        picks=[],
        now=datetime(2026, 11, 12, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    written = me.diff_snapshot(
        _snapshot([("Greyville", 1, "Bright Comet", 3.0)],
                  ts="2026-11-13T10:00:00"),
        picks=[],
        now=datetime(2026, 11, 13, 10, 0),
        baseline_path=store["baseline_path"],
        events_path=store["events_path"],
    )
    assert written == []


def test_writes_are_atomic(store):
    """A temp file must never be left behind."""
    me.append_events([{"id": "a", "ts": datetime.now().isoformat(),
                       "kind": me.KIND_PRICE_MOVE}],
                     path=store["events_path"])
    assert store["events_path"].exists()
    assert not os.path.exists(str(store["events_path"]) + ".tmp")
