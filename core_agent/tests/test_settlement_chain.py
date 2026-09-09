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
    settled = asyncio.run(go("Winner: Other Horse (1st) in race 4 at Vaal"))
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
