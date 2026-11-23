"""Off-time bug: a stale Betfair bf_off_time must not keep a passed race alive.

Scottsville R1 (2026-11-22): Betway t=11:07 UTC, Betfair bf_off_time=13:40 SAST
(= 11:40 UTC). The old closer trusted bf_off_time unconditionally, so the
5-minute grace ran to 11:45 UTC and a race that had already gone off stayed on
the dashboard for another 38 minutes.
"""

from datetime import datetime, timedelta, timezone

from core_agent.core.adaptive_odds_monitor import (
    _close_overdue_races,
    _resolve_race_off_utc,
)


def _utc(ts):
    return ts.replace(tzinfo=None)


def test_earlier_plausible_clock_wins(monkeypatch):
    now = _utc(datetime(2026, 11, 22, 11, 43, tzinfo=timezone.utc))
    event = {"t": "11:07", "bf_off_time": "13:40"}  # BF = 11:40 UTC
    assert _resolve_race_off_utc(event, now) == datetime(2026, 11, 22, 11, 7)


def test_betfair_only_event_still_works():
    now = _utc(datetime(2026, 11, 22, 11, 43, tzinfo=timezone.utc))
    assert _resolve_race_off_utc({"bf_off_time": "13:40"}, now) == datetime(
        2026, 11, 22, 11, 40
    )


def test_betway_only_event_is_parsed_as_utc():
    now = _utc(datetime(2026, 11, 22, 11, 43, tzinfo=timezone.utc))
    assert _resolve_race_off_utc({"t": "11:07"}, now) == datetime(2026, 11, 22, 11, 7)


def test_placeholder_betway_time_is_ignored():
    now = _utc(datetime(2026, 11, 22, 11, 43, tzinfo=timezone.utc))
    event = {"t": "00:00", "bf_off_time": "13:40"}
    # 00:00 is 11h away -> rejected; Betfair's 11:40 UTC is used instead.
    assert _resolve_race_off_utc(event, now) == datetime(2026, 11, 22, 11, 40)


def test_wild_disagreement_picks_clock_nearest_now():
    now = _utc(datetime(2026, 11, 22, 11, 43, tzinfo=timezone.utc))
    event = {"t": "16:00", "bf_off_time": "13:40"}  # gap 4h20 > 3h
    assert _resolve_race_off_utc(event, now) == datetime(2026, 11, 22, 11, 40)


def test_races_after_sast_midnight_are_deferred():
    """A 22:14 UTC race is 00:14 SAST tomorrow — not on today's card."""
    now = _utc(datetime(2026, 11, 23, 20, 0, tzinfo=timezone.utc))
    out = _close_overdue_races(
        {"zia": {"en": "USA: Zia Park", "raceNumber": 8, "t": "22:14"}},
        now_utc=now,
    )
    assert "zia" not in out


def test_hours_old_betway_time_is_TRUSTED_not_treated_as_placeholder():
    """A 06:34 race seen at 13:33 must be dropped, not kept on a TTL."""
    now = _utc(datetime(2026, 11, 22, 13, 33, tzinfo=timezone.utc))
    assert _resolve_race_off_utc({"t": "06:34"}, now) == datetime(2026, 11, 22, 6, 34)
    out = _close_overdue_races(
        {"aus": {"en": "Australia: Kilmore", "raceNumber": 9, "t": "06:34"}},
        max_minutes_after_off=5,
        now_utc=now,
    )
    assert "aus" not in out, "a 7h-past race must not survive as a first_seen ghost"


def test_passed_race_is_dropped_even_when_betfair_time_is_later():
    now = datetime.now(timezone.utc)
    off = (now - timedelta(minutes=40)).replace(second=0, microsecond=0)
    # Betfair claims the race goes off 33 minutes later than Betway's t.
    bf_sast = off + timedelta(hours=2, minutes=33)
    event = {
        "en": "South Africa: Scottsville",
        "raceNumber": 1,
        "t": off.strftime("%H:%M"),
        "bf_off_time": bf_sast.strftime("%H:%M"),
    }
    out = _close_overdue_races({"r1": event}, max_minutes_after_off=5)
    assert "r1" not in out, "a 40-min-past race must not survive on a stale BF clock"


def test_expires_at_is_stamped_from_betway_clock():
    now = datetime.now(timezone.utc)
    off = (now - timedelta(minutes=2)).replace(second=0, microsecond=0)
    bf_sast = off + timedelta(hours=2, minutes=33)
    event = {
        "en": "South Africa: Scottsville",
        "raceNumber": 2,
        "t": off.strftime("%H:%M"),
        "bf_off_time": bf_sast.strftime("%H:%M"),
    }
    out = _close_overdue_races({"r2": event}, max_minutes_after_off=5)
    assert "r2" in out
    expected = off.replace(tzinfo=timezone.utc).timestamp() + 300
    assert out["r2"]["expires_at"] == expected
