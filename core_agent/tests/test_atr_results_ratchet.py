"""ATR results feed: the "finished day" ratchet and the empty-results gate.

Nov-2026 regression, two faults that together froze the feed for 19 hours:

1. **The ratchet.** ``_atr_day_needs_finishing`` declared a day finished as
   soon as it had been quiet for 6h. 2026-11-10 stopped being written at 12:20
   with 8 of ~113 races captured, so by 18:20 the day looked "done" and ATR
   was never asked about it again — the Lingfield / Fairyhouse evening cards
   were lost and their picks sat PENDING until the day-7 expiry.

2. **The write gate.** The snapshot was only rewritten when the merged result
   set was non-empty. Before the first UK meeting (off ~13:00 SAST) every cycle
   parsed a card-only page, wrote nothing, and the snapshot aged all morning —
   while the staleness alarm repeated the same "19h stale" message.

The contract pinned here: a day may only be called finished when the feed was
still *watching* it after it ended, "blocked" is never recorded as "checked",
and a real-but-empty page is bookkeeping, not a snapshot rewrite.
"""
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone

import pytest

from core_agent.core import adaptive_odds_monitor as mon


DAY = "2026-11-10"
DAY_END = mon._atr_day_end_ts(DAY)  # 2026-11-11 04:00 UTC
AFTER_CARD = datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc).timestamp()


def _write_snapshot(path, *, day, races, grew_at, timestamp=None):
    """A results snapshot whose `captured` map says: day had `races` at `grew_at`."""
    courses = [f"Course {i}" for i in range(min(races, 3))] or ["Greyville (RSA)"]
    payload = {
        "results": [
            {"date": day, "course": courses[i % len(courses)], "race_number": i + 1}
            for i in range(races)
        ],
        "captured": {
            day: {
                "races": races,
                "courses": courses,
                "signature": "sig",
                "first_seen_at": grew_at,
                "last_grew_at": grew_at,
            }
        },
        "timestamp": timestamp or datetime.fromtimestamp(grew_at).isoformat(),
    }
    path.write_text(json.dumps(payload))
    return path


def _write_checks(path, days, *, last_success=None, error=None):
    payload = {"days": days}
    if last_success is not None:
        payload["last_success"] = last_success
    if error:
        payload["last_error"] = error
    path.write_text(json.dumps(payload))
    return path


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Never touch the real data volume from a unit test."""
    monkeypatch.setattr(mon, "ATR_RESULTS_CHECKS_PATH", tmp_path / "atr_results_checks.json")
    monkeypatch.setattr(mon, "ATR_RESULTS_PATH", tmp_path / "atr_results_snapshot.json")
    monkeypatch.setattr(mon, "ATR_MOVERS_PATH", tmp_path / "atr_movers_snapshot.json")
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", tmp_path / "atr_predictor_snapshot.json")


# --- 1. the ratchet -------------------------------------------------------


def test_legacy_snapshot_without_capture_map_still_needs_finishing(tmp_path):
    """No `captured` map = no evidence of completion; keep fetching."""
    path = tmp_path / "legacy.json"
    path.write_text(json.dumps({"results": [{"date": DAY, "course": "Vaal (RSA)"}]}))

    assert mon._atr_day_needs_finishing(path, DAY, now_ts=AFTER_CARD) is True


def test_day_frozen_early_is_never_declared_finished(tmp_path):
    """Regression: 2026-11-10 froze at 12:20 with 8 of ~113 races.

    The day was quiet for 6h, so the old rule called it finished and the
    evening UK cards could never be captured. Nothing recorded a poll of the
    day after it ended, so it must stay open.
    """
    snap = _write_snapshot(
        tmp_path / "atr_results_snapshot.json",
        day=DAY,
        races=8,
        grew_at=AFTER_CARD - 24 * 3600,
    )

    assert mon._atr_day_last_checked(DAY) == 0.0
    assert mon._atr_day_needs_finishing(snap, DAY, now_ts=AFTER_CARD) is True


def test_day_watched_after_its_end_and_quiet_is_finished(tmp_path):
    """Once polled past the day's end and quiet for 6h, stop re-fetching."""
    snap = _write_snapshot(
        tmp_path / "atr_results_snapshot.json",
        day=DAY,
        races=113,
        grew_at=AFTER_CARD - 8 * 3600,
    )
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {DAY: {"last_checked_at": DAY_END + 3600, "races_seen": 113}},
    )

    assert mon._atr_day_needs_finishing(snap, DAY, now_ts=AFTER_CARD) is False


def test_day_watched_but_still_growing_needs_finishing(tmp_path):
    """A card that grew inside the quiet window is still running."""
    snap = _write_snapshot(
        tmp_path / "atr_results_snapshot.json",
        day=DAY,
        races=113,
        grew_at=AFTER_CARD - 3600,
    )
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {DAY: {"last_checked_at": DAY_END + 3600, "races_seen": 113}},
    )

    assert mon._atr_day_needs_finishing(snap, DAY, now_ts=AFTER_CARD) is True


def test_day_never_captured_needs_finishing(tmp_path):
    snap = tmp_path / "atr_results_snapshot.json"
    snap.write_text(json.dumps({"results": [], "captured": {}, "timestamp": None}))

    assert mon._atr_day_needs_finishing(snap, DAY, now_ts=AFTER_CARD) is True


# --- 2. poll bookkeeping --------------------------------------------------


def test_note_checks_records_days_races_and_success():
    mon._atr_note_checks(["2026-11-10", "2026-11-11"], {"2026-11-11": 0}, now_ts=1000.0)

    blob = json.loads(mon.ATR_RESULTS_CHECKS_PATH.read_text())
    assert blob["days"]["2026-11-10"] == {"last_checked_at": 1000.0}
    assert blob["days"]["2026-11-11"] == {"last_checked_at": 1000.0, "races_seen": 0}
    assert blob["last_success"] == 1000.0
    assert "last_error" not in blob

    mon._atr_note_checks([], {}, error="today: no page", now_ts=2000.0)

    blob = json.loads(mon.ATR_RESULTS_CHECKS_PATH.read_text())
    assert blob["last_error"] == "today: no page"
    assert blob["last_attempt"] == 2000.0
    # A failed poll must not refresh "we reached the page".
    assert blob["last_success"] == 1000.0
    assert blob["days"]["2026-11-11"]["last_checked_at"] == 1000.0


# --- 3. lull detection (alarm suppression) --------------------------------


def test_note_checks_prunes_days_older_than_the_keep_window():
    """The checks file is bookkeeping, not an archive — keep it bounded."""
    now = datetime.now().timestamp()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {
            "2026-01-01": {"last_checked_at": now - mon.ATR_CHECKS_KEEP_SECS - 60},
            datetime.now().date().isoformat(): {"last_checked_at": now},
        },
    )

    mon._atr_note_checks([datetime.now().date().isoformat()], {}, now_ts=now)

    days = json.loads(mon.ATR_RESULTS_CHECKS_PATH.read_text())["days"]
    assert "2026-01-01" not in days
    assert datetime.now().date().isoformat() in days


def _yesterday_closed(*, raced=0):
    """Snapshot + checks proving yesterday's card was watched to its end."""
    yesterday = mon._atr_yesterday_iso()
    snap = _write_snapshot(
        mon.ATR_RESULTS_PATH,
        day=yesterday,
        races=raced,
        # Quiet for the whole window (9h), whatever the wall clock says now.
        grew_at=datetime.now().timestamp() - 9 * 3600,
    )
    today = datetime.now().date().isoformat()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {
            today: {"last_checked_at": datetime.now().timestamp(), "races_seen": 0},
            yesterday: {
                "last_checked_at": mon._atr_day_end_ts(yesterday) + 60,
                "races_seen": raced,
            },
        },
        last_success=datetime.now().timestamp(),
    )
    return snap


def test_lull_true_when_polling_fine_with_nothing_run_yet():
    _yesterday_closed(raced=113)

    assert mon._atr_results_lull() is True


def test_lull_false_while_yesterday_is_still_owed_a_fetch():
    """A quiet morning is only quiet if last night's card is accounted for.

    Evening cards run to ~06:00 SAST; while yesterday still needs finishing,
    an old results snapshot is a warning, not a lull.
    """
    today = datetime.now().date().isoformat()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {today: {"last_checked_at": datetime.now().timestamp(), "races_seen": 0}},
        last_success=datetime.now().timestamp(),
    )
    assert mon._atr_day_needs_finishing(
        mon.ATR_RESULTS_PATH, mon._atr_yesterday_iso()
    ) is True

    assert mon._atr_results_lull() is False


def test_lull_false_when_races_are_landing():
    today = datetime.now().date().isoformat()
    _yesterday_closed()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {today: {"last_checked_at": datetime.now().timestamp(), "races_seen": 12}},
        last_success=datetime.now().timestamp(),
    )

    assert mon._atr_results_lull() is False


def test_lull_false_when_last_poll_failed():
    today = datetime.now().date().isoformat()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {today: {"last_checked_at": datetime.now().timestamp(), "races_seen": 0}},
        last_success=datetime.now().timestamp(),
        error="today: no page (blocked or throttled)",
    )

    assert mon._atr_results_lull() is False


def test_lull_false_when_we_stopped_reaching_the_page():
    """An hour without a successful poll is an outage, not a lull."""
    today = datetime.now().date().isoformat()
    _write_checks(
        mon.ATR_RESULTS_CHECKS_PATH,
        {today: {"last_checked_at": datetime.now().timestamp(), "races_seen": 0}},
        last_success=datetime.now().timestamp() - 2 * 3600,
    )

    assert mon._atr_results_lull() is False


# --- 4. the refresh path: blocked vs empty vs real ------------------------


class _FakeATR:
    """Fake that mirrors the real `_last_results_page_ok` contract."""

    def __init__(self, pages):
        # pages: {"today": (page_ok, [races]), "yesterday": (...)}
        self.pages = pages
        self.calls = []
        self.bursts = []
        self._last_results_page_ok = True

    def open_stealth_burst(self, pages):
        self.bursts.append(pages)

    async def get_results(self, day):
        self.calls.append(("results", day))
        ok, races = self.pages.get(day, (True, []))
        self._last_results_page_ok = ok
        return list(races)

    async def get_market_movers(self):
        self.calls.append(("movers",))
        return [{"horse": "Eagle Has Landed"}]

    async def get_predictor(self):
        self.calls.append(("predictor",))
        return [{"horse": "Eagle Has Landed"}]


def _harness(monkeypatch, pages):
    atr = _FakeATR(pages)
    monitor = object.__new__(mon.AdaptiveOddsMonitor)
    monitor.at_races = atr
    state = {"reloads": 0, "commits": 0}

    monkeypatch.setattr(monitor, "_volume_reload", lambda: state.__setitem__("reloads", 1))
    monkeypatch.setattr(monitor, "_volume_commit", lambda: state.__setitem__("commits", state["commits"] + 1))
    monkeypatch.setattr(mon, "_atr_snapshot_fresh", lambda *a, **k: False)
    monkeypatch.setattr(mon, "_atr_file_fresh", lambda p, *a, **k: p in (mon.ATR_MOVERS_PATH, mon.ATR_PREDICTOR_PATH))
    monkeypatch.setattr(mon, "_atr_predictor_fresh", lambda *a, **k: True)
    return atr, monitor, state


def test_blocked_poll_is_not_booked_as_a_check(monkeypatch):
    """A 403 that returns [] must not look like "we looked, nothing ran"."""
    atr, monitor, state = _harness(monkeypatch, {"today": (False, []), "yesterday": (False, [])})

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert not mon.ATR_RESULTS_PATH.exists()
    blob = json.loads(mon.ATR_RESULTS_CHECKS_PATH.read_text())
    assert blob["days"] == {}
    assert "no page" in blob["last_error"]
    assert "last_success" not in blob
    assert state["commits"] == 1  # bookkeeping still needs to survive the container


def test_real_but_empty_page_records_check_without_rewriting_snapshot(monkeypatch):
    """The write-gate fix: before the first race, record the poll, not a snapshot.

    Rewriting the snapshot here is what the old gate refused to do — and it was
    right to refuse: a bumped mtime would silence the 45-min freshness gate
    during a live card.
    """
    atr, monitor, state = _harness(monkeypatch, {"today": (True, []), "yesterday": (True, [])})

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert not mon.ATR_RESULTS_PATH.exists()
    today = datetime.now().date().isoformat()
    blob = json.loads(mon.ATR_RESULTS_CHECKS_PATH.read_text())
    assert blob["days"][today]["races_seen"] == 0
    assert blob["last_success"] > 0
    assert state["commits"] == 1


def test_yesterday_results_still_written_when_today_is_empty(monkeypatch):
    """The other half of the gate fix: a quiet "today" must not block writes.

    Before the fix the gate was `if results:` — one empty day short-circuited
    the whole merge, so a yesterday card that had just finished was dropped
    and its picks stayed PENDING.
    """
    yesterday = (datetime.now() - timedelta(days=1)).date().isoformat()
    atr, monitor, state = _harness(
        monkeypatch,
        {
            "today": (True, []),
            "yesterday": (
                True,
                [
                    {"date": yesterday, "course": "Lingfield (GB)", "race_number": 3},
                    {"date": yesterday, "course": "Fairyhouse (IRE)", "race_number": 5},
                ],
            ),
        },
    )

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert mon.ATR_RESULTS_PATH.exists()
    snap = json.loads(mon.ATR_RESULTS_PATH.read_text())
    assert snap["captured"][yesterday]["races"] == 2
    assert {r["course"] for r in snap["results"]} == {"Lingfield (GB)", "Fairyhouse (IRE)"}
    assert state["commits"] == 1


# --- 5. the burst must fund a page per results day ------------------------


def test_burst_funds_a_page_per_results_day(monkeypatch):
    """Two pages need two slots: today must not eat yesterday's allowance.

    Nov-2026: the burst counted the results *feed* once, so the single hourly
    browser fetch always went to "today" and a still-running evening card was
    starved every cycle — the day could never be finished.
    """
    atr, monitor, _ = _harness(
        monkeypatch, {"today": (True, []), "yesterday": (True, [])}
    )

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert atr.bursts == [2]


def test_burst_funds_one_page_once_yesterday_is_finished(monkeypatch):
    atr, monitor, _ = _harness(monkeypatch, {"today": (True, [])})
    _yesterday_closed(raced=113)

    asyncio.run(monitor._refresh_atr_feeds({"events": {}}))

    assert [c for c in atr.calls if c[0] == "results"] == [("results", "today")]
    assert atr.bursts == [1]
