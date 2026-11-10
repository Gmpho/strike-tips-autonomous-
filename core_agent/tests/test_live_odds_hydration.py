"""Live-odds hydration from the market snapshot (Nov-2026).

The SA cards carry no prices, so the value prompt used to send ``odds: null``
and the model invented a flat 5.0 for every runner. The market snapshot has
the real prices — but only races we can prove belong to today may price
today's runners.

The proof is Betfair's ``bf_event_date`` stamp, which is intermittent: when
it was missing the hydration silently produced nothing and the whole meeting
came back priced at 5.0. The snapshot's own write date (in SAST) is the
second, independent proof.
"""
import json
import os

from core_agent.core.strike_tips import _snapshot_live_odds

TODAY = "2026-11-10"


def _write(tmp_path, snap):
    path = os.path.join(str(tmp_path), "market_snapshot_latest.json")
    with open(path, "w") as f:
        json.dump(snap, f)
    return tmp_path


def _event(**kw):
    base = {"course": "Kenilworth", "raceNumber": 2, "t": "11:07",
            "runners": [{"name": "Peach Cobbler", "odds": 2.6},
                        {"name": "Ghost", "odds": 9.0}]}
    base.update(kw)
    return base


def test_betfair_dated_race_is_priced(tmp_path):
    _write(tmp_path, {"timestamp": "2026-11-10T06:00:00",
                      "events": {"1": _event(bf_event_date=TODAY,
                                             bf_off_time="11:07")}})
    prices = _snapshot_live_odds(str(tmp_path), TODAY)
    assert prices[("kenilworth", 2)]["peachcobbler"] == 2.6


def test_undated_race_is_priced_when_the_snapshot_is_todays(tmp_path):
    """No Betfair stamp, but the card was written today and pruned live."""
    _write(tmp_path, {"timestamp": "2026-11-10T06:00:00",
                      "events": {"1": _event()}})
    prices = _snapshot_live_odds(str(tmp_path), TODAY)
    assert prices[("kenilworth", 2)]["peachcobbler"] == 2.6


def test_undated_race_in_a_stale_snapshot_is_not_priced(tmp_path):
    """Yesterday's card must never price today's runners."""
    _write(tmp_path, {"timestamp": "2026-11-09T20:00:00",
                      "events": {"1": _event()}})
    assert _snapshot_live_odds(str(tmp_path), TODAY) == {}


def test_yesterdays_dated_race_is_not_priced(tmp_path):
    _write(tmp_path, {"timestamp": "2026-11-10T06:00:00",
                      "events": {"1": _event(bf_event_date="2026-11-09",
                                             bf_off_time="11:07")}})
    assert _snapshot_live_odds(str(tmp_path), TODAY) == {}


def test_finished_race_is_not_priced(tmp_path):
    _write(tmp_path, {"timestamp": "2026-11-10T06:00:00",
                      "events": {"1": _event(bf_event_date=TODAY,
                                             bf_off_time="11:07",
                                             isFinished=True)}})
    assert _snapshot_live_odds(str(tmp_path), TODAY) == {}


def test_snapshot_stamp_is_read_as_sast(tmp_path):
    # 23:30 UTC on the 9th is already the 10th in South Africa.
    _write(tmp_path, {"timestamp": "2026-11-09T23:30:00",
                      "events": {"1": _event()}})
    prices = _snapshot_live_odds(str(tmp_path), TODAY)
    assert ("kenilworth", 2) in prices
