"""ATR live results: page-date stamping, dedupe, finished-only, and feed order.

Nov-2026 outage pinned here:

* ``/results`` came back as a ~3KB Fastly challenge shell because the browser
  snapshot was taken before the proof-of-work ran, so the feed looked blocked
  while the real page (800KB) was one ``wait`` away.
* The monitor fetched ``yesterday`` first and that single hourly browser slot
  was the whole allowance, so ``today`` was always throttled -> the HUD only
  ever showed yesterday's racing.
* The results page nests ``.push--x-small`` inside itself, so every race was
  appended once per nesting level (612 races for ~26 meetings).
* Entries carried ``date: "yesterday"``. Merged into a newer snapshot they
  re-dated themselves against the new timestamp and mis-settled picks.
* A card fetched before the off lists races with no placings (135 races,
  0 positions), which must never enter the snapshot.
"""
import asyncio
import json

import pytest

from core_agent.core import adaptive_odds_monitor as mon
from core_agent.skills.parsers import attheraces_api as atr

needs_selector = pytest.mark.skipif(
    not atr._SELECTOR_AVAILABLE,
    reason="scrapling Selector unavailable (host lacks it; Docker/Modal runs this)",
)

DAY = "2026-11-08"


def _runner(position, name, odds):
    pos = (
        f'<span class="text-color--neutral">{position}<span class="silk silk--inline">'
        f'<img src="x.png"></span>(10)</span>'
        if position
        else ""
    )
    return (
        '<div class="runner">'
        f'<a class="h7 a--plain tooltip" href="/form/horse/{name}">'
        f"{pos}<span>{name}</span>"
        f'<span class="text-color--neutral">{odds}</span>'
        "</a></div>"
    )


def _article(race_no, clock, horses, placed=True):
    rows = "".join(
        _runner(("1st", "2nd", "3rd")[i] if placed else "", name, odds)
        for i, (name, odds) in enumerate(horses)
    )
    return (
        '<article class="panel-content--medium">'
        f"<header><h3>{race_no}\n{clock} - Some Handicap</h3></header>"
        f'<div class="list list--divided list--padded">{rows}</div>'
        "</article>"
    )


def _meeting(course, body):
    return (
        '<div class="push--x-small">'
        f'<a class="panel-header"><h2>{course} Results</h2></a>'
        f"{body}</div>"
    )


def _page(meetings, day=DAY):
    picker = f'<input type="text" name="race-nav-datepicker" id="race-nav-datepicker" value="{day}" readonly="readonly">' if day else ""
    # >10KB so get_results() does not treat the body as a bot block.
    filler = "<!-- " + ("x" * 12000) + " -->"
    return f"<html><head>{picker}</head><body>{meetings}{filler}</body></html>".encode()


def _parse(html, day="today"):
    api = atr.AtTheRacesAPI()
    api._fetch = lambda path: html  # no network
    return asyncio.run(api.get_results(day))


@needs_selector
def test_nested_containers_do_not_duplicate_races():
    races = [
        _article(1, "12:30", [("Alpha", "5/2"), ("Bravo", "4/1")]),
        _article(2, "13:05", [("Charlie", "7/4"), ("Delta", "9/2")]),
    ]
    body = "".join(races)
    # The real page nests .push--x-small inside itself: same articles twice.
    html = _page(_meeting("Kenilworth (RSA)", body) + _meeting("Kenilworth (RSA)", body))

    parsed = _parse(html)

    assert len(parsed) == 2, [r["title"] for r in parsed]
    assert {r["title"].split("\n")[0] for r in parsed} == {"1", "2"}


@needs_selector
def test_richest_parse_wins_when_a_race_repeats():
    thin = _article(1, "12:30", [("Alpha", "5/2")])
    full = _article(1, "12:30", [("Alpha", "5/2"), ("Bravo", "4/1"), ("Charlie", "8/1")])
    html = _page(_meeting("Greyville", thin) + _meeting("Greyville", full))

    parsed = _parse(html)

    assert len(parsed) == 1
    assert len(parsed[0]["runners"]) == 3


@needs_selector
def test_unplaced_cards_are_dropped():
    """A pre-race card lists runners with no finishing positions."""
    html = _page(
        _meeting(
            "Ffos Las",
            _article(1, "12:50", [("Alpha", "5/2"), ("Bravo", "4/1")], placed=False)
            + _article(2, "13:20", [("Charlie", "2/1"), ("Delta", "6/1")]),
        )
    )

    parsed = _parse(html)

    assert len(parsed) == 1
    assert parsed[0]["title"].startswith("2")


@needs_selector
def test_date_comes_from_the_page_not_the_request_label():
    html = _page(_meeting("Naas (IRE)", _article(1, "12:30", [("Alpha", "5/2")])))

    parsed = _parse(html, day="today")

    assert parsed[0]["date"] == DAY


@needs_selector
def test_date_falls_back_to_the_requested_day():
    from datetime import date, timedelta

    html = _page(
        _meeting("Dundalk", _article(1, "17:30", [("Alpha", "5/2")])),
        day=None,
    )

    parsed = _parse(html, day="yesterday")

    assert parsed[0]["date"] == (date.today() - timedelta(days=1)).isoformat()


@needs_selector
def test_settlement_reads_the_stamped_iso_date():
    from core_agent.skills.league.settlement import _atr_date

    html = _page(_meeting("Aintree", _article(4, "14:25", [("Klimt Madrik", "2/1")])))
    parsed = _parse(html)

    assert _atr_date(parsed[0]["date"], None) == DAY


# ── monitor: feed order, once-a-day yesterday, merge safety ────────────────


class _FakeATR:
    def __init__(self):
        self.calls = []

    async def get_results(self, day):
        self.calls.append(day)
        return [{
            "course": "Greyville",
            "date": mon._atr_yesterday_iso() if day == "yesterday" else DAY,
            "time": "12:30",
            "title": "1\n12:30 - Some Handicap",
            "runners": [{"name": "Alpha", "position": "1st"}],
        }]

    async def get_market_movers(self):
        return [{"horse": "x"}]

    async def get_predictor(self):
        return [{"horse": "x"}]


@pytest.fixture
def monitor(monkeypatch, tmp_path):
    atr_api = _FakeATR()
    m = object.__new__(mon.AdaptiveOddsMonitor)
    m.at_races = atr_api

    results_path = tmp_path / "atr_results_snapshot.json"
    monkeypatch.setattr(mon, "ATR_RESULTS_PATH", str(results_path))
    monkeypatch.setattr(mon, "ATR_MOVERS_PATH", str(tmp_path / "movers.json"))
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(tmp_path / "predictor.json"))
    monkeypatch.setattr(m, "_volume_reload", lambda: None)
    monkeypatch.setattr(m, "_volume_commit", lambda: None)
    monkeypatch.setattr(mon, "_atr_snapshot_fresh", lambda *a, **k: False)
    monkeypatch.setattr(mon, "_atr_file_fresh", lambda p, *a, **k: p != str(results_path))

    writes = {}
    monkeypatch.setattr(
        mon, "_atomic_write_json", lambda path, data, indent=2: writes.__setitem__(path, data)
    )
    return atr_api, m, results_path, writes


def test_today_is_fetched_before_yesterday(monitor):
    atr_api, m, _, _ = monitor

    asyncio.run(m._refresh_atr_feeds({"events": {}}))

    assert atr_api.calls == ["today", "yesterday"]


def test_yesterday_is_not_refetched_once_captured(monitor):
    atr_api, m, results_path, _ = monitor
    results_path.write_text(json.dumps({"results": [{
        "course": "Greyville",
        "date": mon._atr_yesterday_iso(),
        "title": "1\n12:30 - Some Handicap",
        "runners": [{"name": "Alpha", "position": "1st"}],
    }], "timestamp": "2026-11-07T00:00:00"}))

    asyncio.run(m._refresh_atr_feeds({"events": {}}))

    assert atr_api.calls == ["today"]


def test_merge_keeps_absolute_dates_and_dedupes():
    old = {"course": "Aintree", "date": "2026-11-06", "title": "5\n17:00 - Hurdle",
           "runners": [{"name": "Old", "position": "1st"}]}
    fresh = {"course": "Aintree", "date": "2026-11-08", "title": "5\n17:00 - Hurdle",
             "runners": [{"name": "New", "position": "1st"}]}
    same_race_corrected = {"course": "Aintree", "date": "2026-11-08", "title": "5\n17:00 - Hurdle",
                           "runners": [{"name": "New", "position": "1st"}, {"name": "Second", "position": "2nd"}]}

    merged = mon._atr_merge_results([old], [fresh, same_race_corrected])

    dates = sorted(r["date"] for r in merged)
    assert dates == ["2026-11-06", "2026-11-08"]
    corrected = next(r for r in merged if r["date"] == "2026-11-08")
    assert len(corrected["runners"]) == 2


def test_merge_prunes_snapshots_older_than_the_window():
    stale = {"course": "Greyville", "date": "2020-01-01", "title": "1\n12:30 - Old",
             "runners": [{"name": "Alpha", "position": "1st"}]}
    fresh = {"course": "Greyville", "date": DAY, "title": "1\n12:30 - New",
             "runners": [{"name": "Bravo", "position": "1st"}]}

    merged = mon._atr_merge_results([stale], [fresh])

    assert [r["date"] for r in merged] == [DAY]


def test_legacy_relative_labels_are_absolutized_against_their_snapshot():
    legacy = [
        {"course": "Aintree", "date": "yesterday", "title": "5\n17:00 - Hurdle"},
        {"course": "Aintree", "date": "today", "title": "1\n13:00 - Chase"},
    ]

    fixed = mon._atr_absolutize(legacy, "2026-11-07T14:56:15")

    assert [r["date"] for r in fixed] == ["2026-11-06", "2026-11-07"]


def test_snapshot_days_resolves_legacy_labels(monitor):
    _, _, results_path, _ = monitor
    results_path.write_text(json.dumps({
        "results": [{"course": "Aintree", "date": "yesterday", "title": "5\n17:00 - Hurdle"}],
        "timestamp": "2026-11-08T04:40:34",
    }))

    assert mon._atr_snapshot_days(str(results_path)) == {"2026-11-07"}


def test_track_lookup_fetches_the_page_once():
    """Settlement calls this per open pick; a refetch each time burned the
    hourly browser allowance (32 fetches in 2s, Nov-2026)."""
    api = atr.AtTheRacesAPI()
    calls = []

    async def fake_get_results(date="yesterday"):
        calls.append(date)
        return [{"course": "Doncaster", "date": DAY, "title": "1\n11:55 - Maiden",
                 "runners": [{"name": "Alpha", "position": "1st"}]}]

    api.get_results = fake_get_results

    first = asyncio.run(api.get_results_for_track("doncaster", date="yesterday"))
    second = asyncio.run(api.get_results_for_track("doncaster", date="yesterday"))

    assert calls == ["yesterday"]
    assert len(first) == 1 and len(second) == 1
