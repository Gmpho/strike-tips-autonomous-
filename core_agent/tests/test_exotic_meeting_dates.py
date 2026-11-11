"""Exotic tickets must carry the meeting date of their own card.

Nov-2026: TAB publishes the NEXT meeting weeks ahead (Kenilworth and
Turffontein's Saturday cards were served on Wednesday). The scan stamped
every exotic with "today", so the board showed 27 pools under "Today ·
Wed, 11 Nov" — Friday's and Saturday's meetings included. The date is
now taken from the card itself (the live API's ProgramDate, or the date the
racecard PDF states), and each ticket is filed under the day it runs.
"""
import os

from core_agent.core.strike_tips import _merge_exotic_history
from core_agent.skills.parsers.race_dates import (
    meeting_date_from_text as _meeting_date_from_text,
    program_date as _program_date,
)


def _play(track, pool, legs, date=None):
    p = {
        "pool": pool,
        "_track": track,
        "legs": list(legs),
        "combinations": [{"race": legs[0], "banker": "A", "savers": []}],
    }
    if date:
        p["event_date"] = date
    return p


def test_program_date_reads_the_meeting_date():
    assert _program_date({"ProgramDate": "2026-11-13 00:00:00"}) == "2026-11-13"
    assert _program_date({"ProgramDate": "2026-11-13T00:00:00"}) == "2026-11-13"
    assert _program_date({}) is None
    assert _program_date({"ProgramDate": "not-a-date"}) is None


def test_pdf_meeting_date_is_read_from_the_card_text():
    today = __import__("datetime").date.today()
    soon = today.replace(day=today.day) if today.day <= 28 else today
    from datetime import timedelta

    target = today + timedelta(days=3)
    text = f"FAIRVIEW RACECARD {target.day} {target.strftime('%B')} {target.year}\n"
    assert _meeting_date_from_text(text) == target.isoformat()
    # A date far in the past is not this meeting.
    assert _meeting_date_from_text("MEETING 3 January 2019") is None
    assert _meeting_date_from_text("") is None


def test_history_files_each_ticket_under_its_own_meeting_date(tmp_path):
    """Today's card and Saturday's card must land on separate board days."""
    plays = [
        _play("fairview", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-11"),
        _play("kenilworth", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-13"),
    ]
    merged = _merge_exotic_history(str(tmp_path), "2026-11-11", plays)

    days = sorted({str(p.get("event_date")) for p in merged})
    assert days == ["2026-11-11", "2026-11-13"]

    hist = os.path.join(str(tmp_path), "exotics_history.json")
    import json

    with open(hist) as f:
        history = json.load(f)
    by_day = {str(e.get("event_date")): e.get("track") for e in history}
    assert by_day["2026-11-11"] == "fairview"
    assert by_day["2026-11-13"] == "kenilworth"


def test_rescan_of_one_day_keeps_the_other_day(tmp_path):
    """A rescan must not wipe the other meeting's board entry."""
    _merge_exotic_history(
        str(tmp_path), "2026-11-11",
        [
            _play("fairview", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-11"),
            _play("kenilworth", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-13"),
        ],
    )
    merged = _merge_exotic_history(
        str(tmp_path), "2026-11-11",
        [_play("fairview", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-11")],
    )
    tracks = {str(p.get("_track")) for p in merged}
    assert "kenilworth" in tracks      # Saturday's board survived
    assert "fairview" in tracks


def test_a_ticket_refiled_under_its_real_day_does_not_leave_a_stale_copy(tmp_path):
    """A card filed under the wrong day must move, not duplicate."""
    # An earlier scan filed Saturday's card under today.
    _merge_exotic_history(
        str(tmp_path), "2026-11-11",
        [_play("kenilworth", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-11")],
    )
    # The rescan learns the real meeting date and re-files the same ticket.
    merged = _merge_exotic_history(
        str(tmp_path), "2026-11-11",
        [_play("kenilworth", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-13")],
    )

    dates = {str(p.get("event_date")) for p in merged}
    assert dates == {"2026-11-13"}          # moved, not duplicated
    assert len(merged) == 1


def test_the_history_entry_date_wins_over_the_play_copy(tmp_path):
    """The board's day comes from the entry, never from a stale play copy."""
    _merge_exotic_history(
        str(tmp_path), "2026-11-13",
        [_play("kenilworth", "BIPOT", [1, 2, 3, 4, 5, 6], "2026-11-13")],
    )
    # Rewrite the history the way a pre-fix scan wrote it: the play copy
    # still carries the old day.
    import json

    hist = os.path.join(str(tmp_path), "exotics_history.json")
    with open(hist) as f:
        history = json.load(f)
    for entry in history:
        for pool in entry.get("pools") or []:
            pool["event_date"] = "2026-11-11"
    with open(hist, "w") as f:
        json.dump(history, f)

    from core_agent.core.strike_tips import _read_exotic_history

    flat = _read_exotic_history(str(tmp_path))
    assert {str(p.get("event_date")) for p in flat} == {"2026-11-13"}
