"""Settlement chain: ATR date labels, exotic skip, settled-flag honor, bankroll history.

Regression tests for the Sep-2026 settlement-accounting breakdown:
bets stuck PENDING forever, bankroll never moving, analytics empty.
"""
import asyncio
import sys
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.skills.result_tracker import (
    ResultTracker,
    _is_exotic_bet,
    atr_date_label,
)


@pytest.fixture()
def stub_atr_module():
    """Stub the ATR parser module (host CI lacks scrapling/curl deps).

    result_tracker imports it lazily inside _search_result, so injecting
    into sys.modules keeps tests hermetic without touching prod code.
    """
    stub = MagicMock(name="attheraces_api_stub")
    stub_parsers_pkg = MagicMock(name="parsers_pkg_stub")
    with patch.dict(
        sys.modules,
        {
            "core_agent.skills.parsers": stub_parsers_pkg,
            "core_agent.skills.parsers.attheraces_api": stub,
        },
    ):
        yield stub


@pytest.fixture()
def stub_brain_module():
    """Stub strike_brain (host CI lacks dotenv/chromadb); brain=None default."""
    stub = MagicMock(name="strike_brain_stub")
    stub.brain = MagicMock(name="brain_stub")
    stub.brain.strike = None
    with patch.dict(sys.modules, {"core_agent.core.strike_brain": stub}):
        yield stub


# ---------------------------------------------------------------------------
# ATR date label: ISO bet dates -> today/yesterday (never raw ISO into the URL)
# ---------------------------------------------------------------------------
def test_atr_date_label_today():
    assert atr_date_label(date.today().isoformat()) == "today"


def test_atr_date_label_yesterday():
    assert atr_date_label((date.today() - timedelta(days=1)).isoformat()) == "yesterday"


def test_atr_date_label_old_falls_back_to_yesterday():
    # ATR only serves relative pages; never emit a raw ISO string (404s).
    assert atr_date_label((date.today() - timedelta(days=9)).isoformat()) == "yesterday"


def test_atr_date_label_blank_and_garbage():
    assert atr_date_label(None) == "yesterday"
    assert atr_date_label("") == "yesterday"
    assert atr_date_label("not-a-date") == "yesterday"


def test_search_result_uses_label_not_iso(tmp_path, stub_atr_module):
    """The ATR lookup must receive today/yesterday, not '2026-09-04'."""
    seen = {}

    class FakeATR:
        async def get_winner_for_bet(self, track, race_number, date="yesterday"):
            seen["date"] = date
            return {"horse": "Silver Storm", "odds": "3/1"}

    stub_atr_module.AtTheRacesAPI = FakeATR
    tracker = ResultTracker(bankroll_governor=MagicMock())
    text = asyncio.run(tracker._search_result("Vaal", 4, bet_date=date.today().isoformat()))
    assert seen.get("date") == "today"
    assert seen.get("date") != date.today().isoformat()
    assert "Silver Storm" in (text or "")


# ---------------------------------------------------------------------------
# Exotic tickets are skipped (never settled from single-winner results)
# ---------------------------------------------------------------------------
def _bet(**kw):
    b = MagicMock()
    b.bet_id = kw.get("bet_id", "20260101_ABC")
    b.track = kw.get("track", "Vaal")
    b.race_number = kw.get("race_number", 4)
    b.horse = kw.get("horse", "Some Horse")
    b.confidence = kw.get("confidence", "VALUE")
    b.stake = kw.get("stake", 10.0)
    b.actual_return = 0.0
    b.date = date.today().isoformat()
    return b


def test_is_exotic_bet():
    assert _is_exotic_bet(_bet(horse="PICK6:1-2-3-4-5-6", confidence="EXOTIC"))
    assert _is_exotic_bet(_bet(horse="JACKPOT 1:4-5-6-7"))
    assert not _is_exotic_bet(_bet(horse="Silver Storm", confidence="VALUE"))


def test_exotic_open_bet_never_settled(stub_brain_module):
    gov = MagicMock()
    exotic = _bet(horse="PICK6:4-5-6-7-8-9", confidence="EXOTIC")
    gov.get_open_bets.return_value = [exotic]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_search_result", new=AsyncMock(return_value="Winner: X (1st)")
    ) as mock_search:
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert settled == []
    mock_search.assert_not_called()
    gov.settle_bet.assert_not_called()


def test_single_bet_settles_win_and_loss(stub_brain_module):
    gov = MagicMock()
    gov.get_open_bets.return_value = [_bet(horse="Silver Storm")]
    tracker = ResultTracker(bankroll_governor=gov)

    async def go(text):
        with patch.object(
            ResultTracker, "_search_result", new=AsyncMock(return_value=text)
        ):
            return await tracker.check_and_settle_open_bets()

    settled = asyncio.run(go("Winner: Silver Storm (1st) in race 4 at Vaal"))
    assert len(settled) == 1 and settled[0]["won"] is True
    gov.settle_bet.assert_called_once()
    assert gov.settle_bet.call_args[1]["won"] is True

    gov.reset_mock()
    gov.get_open_bets.return_value = [_bet(horse="Silver Storm")]
    settled = asyncio.run(go("Winner: Night Fever (1st) in race 4 at Vaal"))
    assert len(settled) == 1 and settled[0]["won"] is False
    assert gov.settle_bet.call_args[1]["won"] is False


def _bet_on(date_str, **kw):
    kw["date"] = date_str
    b = _bet(**kw)
    b.date = date_str
    return b


def test_old_bet_deferred_not_settled(stub_brain_module):
    """Bets older than 3 days stay PENDING — never settled against the
    wrong (recent) race for the same track+race number."""
    gov = MagicMock()
    old = _bet_on((date.today() - timedelta(days=9)).isoformat(), horse="Old Timer")
    gov.get_open_bets.return_value = [old]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_search_result", new=AsyncMock(return_value="Winner: X (1st)")
    ) as mock_search:
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert settled == []
    mock_search.assert_not_called()
    gov.settle_bet.assert_not_called()
    assert old.status != "WON"  # untouched MagicMock status, never settled


def test_boundary_bet_still_processed(stub_brain_module):
    """Exactly max_age_days old is still eligible (strictly-greater rule)."""
    gov = MagicMock()
    edge = _bet_on((date.today() - timedelta(days=3)).isoformat(), horse="Silver Storm")
    gov.get_open_bets.return_value = [edge]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_search_result",
        new=AsyncMock(return_value="Winner: Silver Storm (1st) in race 4 at Vaal"),
    ):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert len(settled) == 1 and settled[0]["won"] is True


def test_max_age_override(stub_brain_module):
    """Custom max_age_days=0 defers even yesterday's bets."""
    gov = MagicMock()
    gov.get_open_bets.return_value = [
        _bet_on((date.today() - timedelta(days=1)).isoformat(), horse="Silver Storm")
    ]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_search_result", new=AsyncMock(return_value="Winner: X (1st)")
    ) as mock_search:
        settled = asyncio.run(tracker.check_and_settle_open_bets(max_age_days=0))
    assert settled == []
    mock_search.assert_not_called()


def test_unparseable_date_fails_open(stub_brain_module):
    """Bets with garbage dates are settled normally (fail-open)."""
    gov = MagicMock()
    gov.get_open_bets.return_value = [_bet_on("soon", horse="Silver Storm")]
    tracker = ResultTracker(bankroll_governor=gov)
    with patch.object(
        ResultTracker, "_search_result",
        new=AsyncMock(return_value="Winner: Silver Storm (1st) in race 4 at Vaal"),
    ):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert len(settled) == 1 and settled[0]["won"] is True


def test_race_winner_rejects_generic_words():
    tracker = ResultTracker(bankroll_governor=MagicMock())
    assert tracker._extract_race_winner("1st choice by two lengths here") is None
    assert tracker._extract_race_winner("the favourite won easily today") is None
    assert tracker._extract_race_winner("our top pick for the meeting") is None
    # Real names still extract.
    assert tracker._extract_race_winner("Winner: Silver Storm (1st) in race 4 at Vaal") == "Silver Storm"
    assert tracker._extract_race_winner("1st Madison County, odds 3/1, going well") == "Madison County"


def test_off_time_gate_skips_unrun_race(stub_brain_module, tmp_path):
    """A bet whose off-time is in the future is never settled, win or lose."""
    from datetime import datetime, timedelta as _td

    gov = MagicMock()
    gov.get_open_bets.return_value = [_bet(horse="Silver Storm")]
    tracker = ResultTracker(bankroll_governor=gov)
    future = datetime.now() + _td(hours=3)
    past = datetime.now() - _td(hours=3)
    with patch.object(
        ResultTracker, "_race_off_datetime", return_value=future
    ), patch.object(
        ResultTracker, "_search_result", new=AsyncMock(return_value="Winner: Silver Storm (1st)")
    ) as mock_search:
        assert asyncio.run(tracker.check_and_settle_open_bets()) == []
    mock_search.assert_not_called()
    with patch.object(
        ResultTracker, "_race_off_datetime", return_value=past
    ), patch.object(
        ResultTracker, "_search_result",
        new=AsyncMock(return_value="Winner: Silver Storm (1st) in race 4 at Vaal"),
    ):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    assert len(settled) == 1 and settled[0]["won"] is True


def test_race_off_datetime_from_scan_file(tmp_path):
    from datetime import datetime as _dt
    import json

    day = date.today().isoformat()
    (tmp_path / f"daily_scan_{day}.json").write_text(json.dumps({
        "Vaal": [{"race_number": 4, "race_time": "14:05"}]
    }))
    off = ResultTracker._race_off_datetime("vaal", 4, day, data_dir=str(tmp_path))
    assert off is not None and (off.hour, off.minute) == (14, 5)
    assert ResultTracker._race_off_datetime("vaal", 9, day, data_dir=str(tmp_path)) is None
    assert ResultTracker._race_off_datetime("vaal", 4, day, data_dir="/nonexistent") is None


def test_void_settlement_reverses_money(tmp_path):
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    # Real single: placement holds, settle applies P&L, void restores all.
    b = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    gov.settle_bet(b.bet_id, won=False)  # 1000 -> 960
    assert gov.current_bankroll == pytest.approx(960.0)
    assert gov.void_settlement(b.bet_id, notes="phantom") is True
    assert gov.current_bankroll == pytest.approx(1000.0)
    assert gov.total_profit_loss == pytest.approx(0.0)
    assert gov.get_open_bets()[0].status == "PENDING"

    w = gov.record_bet("Vaal", 5, "Beta Two", 3.0, 40.0, 10.0, "VALUE")
    gov.settle_bet(w.bet_id, won=True)  # 1000 -> 1080
    gov.void_settlement(w.bet_id)
    assert gov.current_bankroll == pytest.approx(1000.0)

    # Real exotic: cost deducted at placement; void-LOST refunds it.
    x = gov.record_exotic_bet("Vaal", "JP1", [4, 5], [{"race": 4, "banker": "A", "savers": []}], 10.0, 500.0)
    assert gov.current_bankroll == pytest.approx(1000.0 - 10.0)
    gov.settle_exotic_bet(x.bet_id, pool_return=0.0)
    assert gov.void_settlement(x.bet_id, notes="race not run") is True
    assert gov.current_bankroll == pytest.approx(1000.0)

    # Voiding unknown / already-pending is safe.
    assert gov.void_settlement("nope") is False
    assert gov.void_settlement(x.bet_id) is True  # now PENDING -> True


def test_duplicate_bets_rejected(tmp_path):
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=100000.0)
    first = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    assert first is not None
    assert gov.record_bet("vaal", 4, "alpha one", 3.0, 40.0, 10.0, "VALUE") is None
    # Different race still allowed.
    assert gov.record_bet("Vaal", 5, "Alpha One", 3.0, 40.0, 10.0, "VALUE") is not None

    x1 = gov.record_exotic_bet("Vaal", "JP1", [4, 5], [{"race": 4, "banker": "A", "savers": []}], 10.0, 500.0)
    assert x1 is not None
    assert gov.record_exotic_bet("Vaal", "JP1", [4, 5], [{"race": 4, "banker": "A", "savers": []}], 10.0, 500.0) is None
    assert gov.record_exotic_bet("Vaal", "JP1", [6, 7], [{"race": 6, "banker": "A", "savers": []}], 10.0, 500.0) is not None


def test_exotic_history_merge_and_prune(tmp_path):
    from core_agent.core.strike_tips import _merge_exotic_history, _read_exotic_history

    today = date.today().isoformat()
    old = (date.today() - timedelta(days=2)).isoformat()
    plays_a = [{"pool": "JP1", "legs": [4, 5], "combinations": [], "_track": "Vaal"}]
    plays_b = [{"pool": "PA", "legs": [2, 3], "combinations": [], "_track": "Vaal"}]

    flat = _merge_exotic_history(str(tmp_path), today, plays_a)
    assert len(flat) == 1 and flat[0]["event_date"] == today
    # Same day/track rescan replaces; other track appends.
    plays_b[0]["_track"] = "Turffontein"
    flat = _merge_exotic_history(str(tmp_path), today, plays_b)
    assert sorted(p["pool"] for p in flat) == ["JP1", "PA"]
    # Past entries pruned on read; empty scans must use _read (no wipe).
    import json as _json
    hist = _json.loads((tmp_path / "exotics_history.json").read_text())
    hist.append({"event_date": old, "track": "Vaal", "pools": plays_a, "created_at": old})
    (tmp_path / "exotics_history.json").write_text(_json.dumps(hist))
    flat = _read_exotic_history(str(tmp_path))
    assert all(p["event_date"] >= today for p in flat)
    assert len(flat) == 2


def test_bf_off_time_threading_and_fallback_match(tmp_path):
    """Exact Betfair off-times reach the snapshot even when display times
    disagree, via the course+raceNumber fallback match."""
    import json as _json
    from core_agent.core.adaptive_odds_monitor import _merge_bf_into
    from core_agent.skills.parsers.betfair_sa import BetfairSA

    # Parser emits offTime + raceNumber; t stays stable for display.
    api = BetfairSA()
    ev = api._parse_market("1.1", {
        "runners": [{"runnername": "Horse A", "metadata": {}}],
        "event": {"name": "Vaal", "startTime": 1788387300000},
        "markets": [{"name": "R4 1600m Mdn"}],
    })
    assert ev is not None
    assert ev.get("offTime") is not None and ":" in ev["offTime"]
    assert ev.get("raceNumber") == 4

    ev_none = api._parse_market("1.2", {
        "runners": [{"runnername": "Horse A", "metadata": {}}],
        "event": {"name": "Vaal"},
        "markets": [{"name": "R4 1600m Mdn"}],
    })
    assert ev_none is not None
    assert "offTime" not in ev_none  # unknown stays absent, never fabricated
    assert ev_none["t"] == "00:00"

    # Merge: Betway placeholder time vs exact Betfair time -> fallback match
    # on (course, raceNumber) still merges + stamps bf_off_time.
    state = {"events": {"1": {
        "course": "Vaal", "t": "12:00", "raceNumber": 4,
        "runners": [{"name": "Horse A"}],
    }}}
    bf = {"events": {"mk1": {
        "course": "vaal", "t": "14:05", "raceName": "R4 1600m Mdn",
        "raceNumber": 4, "offTime": "14:05",
        "runners": [{"name": "Horse A", "gear": "Hood"}],
    }}}
    _merge_bf_into(state, bf)
    assert state["events"]["1"]["runners"][0].get("gear") == "Hood"
    assert state["events"]["1"].get("bf_off_time") == "14:05"
    assert state["events"]["1"]["t"] == "12:00"  # display untouched

    # Existing stamp never overwritten.
    state["events"]["1"]["bf_off_time"] = "13:00"
    _merge_bf_into(state, bf)
    assert state["events"]["1"]["bf_off_time"] == "13:00"


def test_find_race_time_prefers_bf_off(tmp_path):
    """Gate uses the exact stamp over scan placeholders."""
    import json as _json
    from core_agent.skills.result_tracker import _find_race_time

    day = date.today().isoformat()
    (tmp_path / f"daily_scan_{day}.json").write_text(_json.dumps({
        "Vaal": [{"race_number": 4, "race_time": "12:00"}]
    }))
    (tmp_path / "market_snapshot_latest.json").write_text(_json.dumps({
        "events": {"1": {
            "course": "Vaal", "t": "12:00", "raceNumber": 4,
            "bf_off_time": "14:05", "runners": [],
        }}
    }))
    assert _find_race_time(str(tmp_path), "vaal", 4, day) == "14:05"
    # Without the stamp, scan time is used.
    (tmp_path / "market_snapshot_latest.json").write_text(_json.dumps({
        "events": {"1": {
            "course": "Vaal", "t": "12:00", "raceNumber": 4, "runners": [],
        }}
    }))
    assert _find_race_time(str(tmp_path), "vaal", 4, day) == "12:00"


def test_daily_report_for_explicit_date_and_aged_section(tmp_path):
    """generate_daily_report(report_date) filters by date and lists the
    aged backlog (PENDING past max age) for manual review."""
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    today = date.today().isoformat()
    old_day = (date.today() - timedelta(days=9)).isoformat()

    settled_bet = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    gov.settle_bet(settled_bet.bet_id, won=True)

    # Back-date an open bet 9 days (stays PENDING, never settled here).
    stale = gov.record_bet("Vaal", 5, "Beta Two", 4.0, 30.0, 12.0, "VALUE")
    stale.date = old_day

    report_today = gov.generate_daily_report()
    assert f"DAILY REPORT FOR {today}" in report_today
    assert "Alpha One" in report_today
    assert "needs manual review" in report_today
    assert "Beta Two" in report_today  # aged section

    report_old = gov.generate_daily_report(report_date=old_day)
    assert f"DAILY REPORT FOR {old_day}" in report_old
    assert "Alpha One" not in report_old.split("Lifetime")[0]
    assert "Beta Two" in report_old  # its open line + aged section


def test_scheduler_has_both_report_jobs():
    apscheduler = pytest.importorskip("apscheduler")
    from core_agent.core.scheduler import StrikeTipsScheduler

    sched = StrikeTipsScheduler()
    try:
        jobs = {j.id: j for j in sched.scheduler.get_jobs()}
        assert "end_of_day_report" in jobs
        assert "morning_report" in jobs

        def _cron_hm(trigger):
            import re
            fields = {f.name: str(f.expressions) for f in trigger.fields}
            return (
                int(re.search(r"\d+", fields["hour"]).group()),
                int(re.search(r"\d+", fields["minute"]).group()),
            )

        assert _cron_hm(jobs["end_of_day_report"].trigger) == (20, 0)
        assert _cron_hm(jobs["morning_report"].trigger) == (7, 0)
    finally:
        try:
            # Never started — shutdown raises SchedulerNotRunningError.
            sched.scheduler.shutdown(wait=False)
        except Exception:
            pass


def test_volume_sync_throttles_and_noops_off_modal(monkeypatch):
    """sync_volume: at most one reload per window; silent no-op without Modal."""
    import core_agent.core.volume_sync as vs

    calls = []
    fake_vol = MagicMock()
    fake_vol.reload.side_effect = lambda: calls.append(1)
    fake_modal = MagicMock()
    fake_modal.Volume.from_name.return_value = fake_vol
    monkeypatch.setitem(sys.modules, "modal", fake_modal)
    monkeypatch.setenv("MODAL_TASK_ID", "task-123")
    vs._last_reload = 0.0
    vs._volume = None

    assert vs.sync_volume(max_age_secs=60) is True
    assert len(calls) == 1
    assert vs.sync_volume(max_age_secs=60) is False  # throttled
    assert len(calls) == 1

    # Outside Modal (local Docker/dev): no-op, never raises.
    monkeypatch.delenv("MODAL_TASK_ID")
    vs._last_reload = 0.0
    assert vs.sync_volume(max_age_secs=0) is False
    assert len(calls) == 1

    # Reload failures (open files) are swallowed, never raised.
    vs._last_reload = 0.0
    monkeypatch.setenv("MODAL_TASK_ID", "task-123")
    fake_vol.reload.side_effect = RuntimeError("open files")
    assert vs.sync_volume(max_age_secs=0) is True


def test_failed_brain_settle_is_not_recorded(stub_brain_module):
    """brain.strike.settle_bet returns a dict — a settled=False dict must not
    count as settled (previously any dict counted as success)."""
    gov = MagicMock()
    gov.get_open_bets.return_value = [_bet(horse="Silver Storm")]
    gov.settle_bet.return_value = True
    tracker = ResultTracker(bankroll_governor=gov)
    fake_strike = MagicMock()
    fake_strike.settle_bet.return_value = {"settled": False}
    stub_brain_module.brain.strike = fake_strike
    with patch.object(
        ResultTracker, "_search_result",
        new=AsyncMock(return_value="Winner: Silver Storm (1st) in race 4 at Vaal"),
    ):
        settled = asyncio.run(tracker.check_and_settle_open_bets())
    # Falls back to governor and records exactly one settle.
    assert len(settled) == 1
    gov.settle_bet.assert_called_once()


# ---------------------------------------------------------------------------
# Bankroll history exists and reconciles with the live balance
# ---------------------------------------------------------------------------
def test_bankroll_history_method_exists_and_reconciles(tmp_path):
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    assert hasattr(gov, "get_bankroll_history")

    # Distinct name prefixes -> distinct bet_ids; stakes within the 5% cap.
    b1 = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    b2 = gov.record_bet("Vaal", 5, "Beta Two", 4.0, 30.0, 12.0, "VALUE")
    assert b1 and b2 and b1.bet_id != b2.bet_id
    gov.settle_bet(b1.bet_id, won=True)   # +80 -> 1080
    gov.settle_bet(b2.bet_id, won=False)  # -30 -> 1050

    assert gov.current_bankroll == pytest.approx(1050.0)
    hist = gov.get_bankroll_history()
    assert hist[0]["t"] == "Start"
    assert hist[0]["balance"] == pytest.approx(1000.0)
    assert hist[-1]["balance"] == pytest.approx(gov.current_bankroll)
    assert [h["t"] for h in hist[1:]] == sorted(h["t"] for h in hist[1:])


def test_bankroll_history_never_negative(tmp_path):
    """Paper refills inject balance with no ledger entry, which can drive the
    backward-reconstructed start below zero — floor the series at 0."""
    import json
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    (tmp_path / "settings.json").write_text(
        json.dumps({"paper_mode": True, "paper_balance": 1000.0})
    )
    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    bet = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    assert bet is not None and bet.is_paper
    gov.settle_bet(bet.bet_id, won=True)  # paper P&L +80
    gov.paper_balance = 10.0  # simulate post-refill drift below lifetime P&L
    gov._save_state()
    hist = gov.get_bankroll_history()
    assert all(h["balance"] >= 0 for h in hist)
    assert hist[0]["balance"] == pytest.approx(0.0)
    assert hist[-1]["balance"] == pytest.approx(10.0)


def test_bankroll_history_empty_is_current_balance(tmp_path):
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    assert gov.get_bankroll_history() == [{"t": "Start", "balance": 1000.0}]


def test_stale_bets_excluded_from_exposure(tmp_path):
    """Aged PENDING bets (finished races awaiting review) are not real
    exposure — excluding them unblocks the governor's daily-limit wall."""
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    fresh = gov.record_bet("Vaal", 4, "Alpha One", 3.0, 40.0, 10.0, "VALUE")
    stale = gov.record_bet("Vaal", 5, "Beta Two", 4.0, 30.0, 12.0, "VALUE")
    stale.date = (date.today() - timedelta(days=9)).isoformat()
    gov._save_state()

    assert gov.get_open_exposure() == pytest.approx(40.0)
    assert gov.get_open_exposure(include_stale=True) == pytest.approx(70.0)

    # Unparseable dates fail open (counted).
    stale.date = "soon"
    gov._save_state()
    assert gov.get_open_exposure() == pytest.approx(70.0)
    assert fresh.bet_id != stale.bet_id


def test_governor_not_walled_by_stale_backlog(tmp_path):
    """R5000 of 9-day-old pending stakes must not block a fresh R40 bet."""
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    old_day = (date.today() - timedelta(days=9)).isoformat()
    for i in range(50):
        # Back-date + persist immediately: record_bet reloads state from disk
        # on entry, which would wipe an unsaved in-memory back-date and trip
        # the wall mid-loop. Gross lands 50 x R50 (5% cap) = R2500.
        b = gov.record_bet("Vaal", 4, f"Stale Horse {i}", 3.0, 100.0, 10.0, "VALUE")
        assert b is not None
        b.date = old_day
        gov._save_state()
    gross = gov.get_open_exposure(include_stale=True)
    assert gross > 200.0  # would trip the 20% daily wall on gross basis
    ok, _reason = gov.can_bet_today(40.0)
    assert ok is True


def test_real_bankroll_moves_on_settle_not_placement(tmp_path):
    """Real-mode: placement holds exposure, settlement moves the balance."""
    from core_agent.skills.bankroll_manager.governor import BankrollGovernor

    gov = BankrollGovernor(data_dir=str(tmp_path), starting_bankroll=1000.0)
    bet = gov.record_bet("Vaal", 4, "Horse A", 3.0, 40.0, 10.0, "VALUE")
    assert bet is not None
    assert gov.current_bankroll == pytest.approx(1000.0)  # held, not deducted
    assert gov.get_open_exposure() == pytest.approx(40.0)
    gov.settle_bet(bet.bet_id, won=True)
    assert gov.current_bankroll == pytest.approx(1080.0)  # +80 net
    assert gov.get_open_exposure() == pytest.approx(0.0)


def test_course_cleaning_and_event_date_parsing():
    from core_agent.skills.parsers.betfair_sa import BetfairSA

    assert BetfairSA._clean_course("Fairview (RSA) 11 Sep") == "Fairview"
    assert BetfairSA._clean_course("Greyville") == "Greyville"
    assert BetfairSA._event_date_from_market({"event": {"name": "Fairview (RSA) 11 Sep"}}) == "2026-09-11"
    assert BetfairSA._event_date_from_market({"event": {"name": "Fairview"}}) is None
    assert BetfairSA._event_date_from_market({}) is None


def test_off_time_prefers_market_start_time():
    from core_agent.skills.parsers.betfair_sa import BetfairSA

    # Real payload shape: top-level marketStartTime (UTC epoch ms).
    # 1789121700000 = 10:15 UTC = 12:15 SAST. The /all timeLabel ("10:15")
    # is UTC — never use it as a local off-time (would shift 2h early).
    assert BetfairSA._off_time_from_market({"marketStartTime": 1789121700000}) == "12:15"
    assert BetfairSA._off_time_from_market({}) is None
    assert BetfairSA._time_from_market({}) == "00:00"


def test_parse_market_carries_event_date():
    from core_agent.skills.parsers.betfair_sa import BetfairSA

    ev = BetfairSA()._parse_market("1.1", {
        "runners": [{"runnername": "Horse A", "metadata": {}}],
        "marketStartTime": 1789121700000,
        "event": {"name": "Fairview (RSA) 11 Sep", "venue": "Fairview"},
        "markets": [{"name": "R1 1000m Mdn"}],
    })
    assert ev is not None
    assert ev["course"] == "Fairview"
    assert ev["offTime"] == "12:15"
    assert ev["eventDate"] == "2026-09-11"
    assert ev["raceNumber"] == 1


def test_merge_stamps_event_date(tmp_path):
    from core_agent.core.adaptive_odds_monitor import _merge_bf_into

    state = {"events": {"1": {
        "course": "Fairview", "t": "10:15", "raceNumber": 1,
        "runners": [{"name": "Horse A"}],
    }}}
    bf = {"events": {"mk1": {
        "course": "Fairview", "t": "10:15", "raceNumber": 1,
        "offTime": "10:15", "eventDate": "2026-09-11",
        "runners": [{"name": "Horse A"}],
    }}}
    _merge_bf_into(state, bf)
    assert state["events"]["1"].get("bf_off_time") == "10:15"
    assert state["events"]["1"].get("bf_event_date") == "2026-09-11"


def test_gate_ignores_other_edition(tmp_path):
    """A market stamped for a different date than the bet must not gate it."""
    import json as _json
    from datetime import datetime as _dt, timedelta as _td
    from core_agent.skills.result_tracker import ResultTracker

    day = date.today().isoformat()
    (tmp_path / "market_snapshot_latest.json").write_text(_json.dumps({
        "events": {"1": {
            "course": "Vaal", "t": "12:00", "raceNumber": 4,
            "bf_off_time": "14:05", "bf_event_date": day, "runners": [],
        }}
    }))
    off = ResultTracker._race_off_datetime("vaal", 4, day, data_dir=str(tmp_path))
    assert off is not None and (off.hour, off.minute) == (14, 5)
    assert off.tzinfo is not None  # SAST-aware: naive UTC comparisons delayed everything 2h

    # Same market, but the bet is from yesterday -> stamp must not apply;
    # falls back to scan file (absent here) -> None, evidence decides.
    other_day = (date.today() - _td(days=1)).isoformat()
    off2 = ResultTracker._race_off_datetime("vaal", 4, other_day, data_dir=str(tmp_path))
    assert off2 is None


def test_number_names_rejected_everywhere():
    from core_agent.skills.parsers.tab4racing import _is_number_name
    from core_agent.core.strike_tips import _is_number_selection, _play_has_real_names

    assert _is_number_name("1") and _is_number_name(" 12 ")
    assert not _is_number_name("THOONSIL") and not _is_number_name("2B")
    assert _is_number_selection("7")
    assert not _is_number_selection("Kensal Green")
    good = {"pool": "JP1", "legs": [4, 5],
            "combinations": [{"race": 4, "banker": "Pressonregardless", "savers": ["Kensal Green"]}],
            "estimated_combinations": 2}
    bad = {"pool": "JP1", "legs": [4, 5],
           "combinations": [{"race": 4, "banker": "1", "savers": ["2"]}],
           "estimated_combinations": 2}
    assert _play_has_real_names(good) is True
    assert _play_has_real_names(bad) is False
    assert _play_has_real_names({"pool": "JP1", "legs": [], "combinations": []}) is True


def test_betfair_distance_parsing():
    from core_agent.skills.parsers.betfair_sa import BetfairSA

    assert BetfairSA._distance_from_market({"markets": [{"name": "R1 1200m Mdn"}]}) == 1200
    assert BetfairSA._distance_from_market({"markets": [{"name": "R6 6f Mdn"}]}) == 1207
    assert BetfairSA._distance_from_market({"markets": [{"name": "R8 1m1f Stks"}]}) == 1811
    assert BetfairSA._distance_from_market({"markets": [{"name": "R4 1400m Mdn"}]}) == 1400
    assert BetfairSA._distance_from_market({"markets": [{"name": "R1 Mdn"}]}) is None
    assert BetfairSA._distance_from_market({}) is None

    ev = BetfairSA()._parse_market("1.1", {
        "runners": [{"runnername": "Horse A", "metadata": {}}],
        "marketStartTime": 1789121700000,
        "event": {"name": "Fairview (RSA) 11 Sep", "venue": "Fairview"},
        "markets": [{"name": "R1 1200m Mdn"}],
    })
    assert ev is not None and ev.get("distanceM") == 1200


def test_merge_stamps_distance():
    from core_agent.core.adaptive_odds_monitor import _merge_bf_into

    state = {"events": {"1": {
        "course": "Fairview", "t": "12:15", "raceNumber": 1,
        "runners": [{"name": "Horse A"}],
    }}}
    bf = {"events": {"mk1": {
        "course": "Fairview", "t": "12:15", "raceNumber": 1,
        "offTime": "12:15", "eventDate": "2026-09-11", "distanceM": 1200,
        "runners": [{"name": "Horse A"}],
    }}}
    _merge_bf_into(state, bf)
    assert state["events"]["1"].get("distance_m") == 1200
    # Existing value never overwritten.
    state["events"]["1"]["distance_m"] = 1000
    _merge_bf_into(state, bf)
    assert state["events"]["1"].get("distance_m") == 1000


def _mk_play(pool, legs, track="Vaal"):
    return {
        "pool": pool, "legs": list(legs),
        "combinations": [{"race": r, "banker": "Horse A", "savers": []} for r in legs],
        "estimated_combinations": 1, "estimated_dividend": 100.0,
        "_track": track,
    }


def test_exotic_layout_validation():
    from core_agent.core.strike_tips import _validate_exotic_layout

    good_jp = _mk_play("JACKPOT 1", [4, 5, 6, 7])
    out_of_range = _mk_play("JACKPOT 2", [7, 8, 9, 10])  # R10 on 9-race card
    wrong_count = _mk_play("PICK 6", [4, 5, 6])  # needs 6 legs
    dupe = _mk_play("JACKPOT 1", [4, 5, 6, 7])
    unknown_family = _mk_play("QUARTET", [1, 2, 3])  # no canonical count: kept
    out = _validate_exotic_layout(
        [good_jp, out_of_range, wrong_count, dupe, unknown_family], 9
    )
    pools = [p["pool"] for p in out]
    assert pools == ["JACKPOT 1", "QUARTET"]
    assert _validate_exotic_layout([], 9) == []
    assert _validate_exotic_layout([good_jp], 0) == [good_jp]  # unknown card: pass through

    # Overlapping ranges across DIFFERENT pools are normal SA structure: kept.
    pa = _mk_play("PLACE ACCUMULATOR", [2, 3, 4, 5, 6, 7, 8])
    p6 = _mk_play("PICK 6", [4, 5, 6, 7, 8, 9])
    out2 = _validate_exotic_layout([pa, p6], 9)
    assert [p["pool"] for p in out2] == ["PLACE ACCUMULATOR", "PICK 6"]
