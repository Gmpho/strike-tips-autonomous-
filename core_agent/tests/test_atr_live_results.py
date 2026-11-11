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
from datetime import date, timedelta

import pytest

from core_agent.core import adaptive_odds_monitor as mon
from core_agent.skills.parsers import attheraces_api as atr

needs_selector = pytest.mark.skipif(
    not atr._SELECTOR_AVAILABLE,
    reason="scrapling Selector unavailable (host lacks it; Docker/Modal runs this)",
)

# Date-relative on purpose: the snapshot merge prunes to a rolling window, so
# an absolute fixture silently rots into a failure once the clock passes it
# (Nov-2026: this file went red on the third day because DAY was pinned).
DAY = (date.today() - timedelta(days=1)).isoformat()
OLDER_DAY = (date.today() - timedelta(days=2)).isoformat()


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
def test_outer_meeting_does_not_claim_foreign_articles():
    """A nested container's articles include later meetings.

    Nov-2026: the Doncaster container wrapped the whole page, so its
    descendant articles included five foreign evening cards and Doncaster
    showed 13 races. Attribution must follow document order, pairing each
    article with the heading that actually precedes it.
    """
    domestic = "".join(
        _article(n, f"1{n}:00", [("Alpha", "5/2")]) for n in range(1, 9)
    )
    foreign = (
        _article(9, "21:14", [("Bravo", "7/2")])
        + _article(10, "22:55", [("Charlie", "9/2")])
    )
    html = _page(
        '<div class="push--x-small">'
        '<a class="panel-header"><h2>Doncaster Results</h2></a>'
        + domestic
        + '<div class="push--x-small">'
        '<a class="panel-header"><h2>Flemington (Australia) Results</h2></a>'
        + foreign
        + "</div></div>"
    )

    parsed = _parse(html)

    by_course = {}
    for race in parsed:
        by_course.setdefault(race["course"], []).append(race["title"].split("\n")[0])
    assert sorted(by_course["Doncaster"]) == [str(n) for n in range(1, 9)]
    assert sorted(by_course["Flemington (Australia)"]) == ["10", "9"]
    assert len(parsed) == 10


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
        self.bursts = []

    def open_stealth_burst(self, pages):
        self.bursts.append(pages)

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
    monkeypatch.setattr(mon, "ATR_RESULTS_CHECKS_PATH", tmp_path / "atr_results_checks.json")
    monkeypatch.setattr(mon, "ATR_MOVERS_PATH", str(tmp_path / "movers.json"))
    monkeypatch.setattr(mon, "ATR_PREDICTOR_PATH", str(tmp_path / "predictor.json"))
    monkeypatch.setattr(m, "_volume_reload", lambda: None)
    monkeypatch.setattr(m, "_volume_commit", lambda: None)
    monkeypatch.setattr(mon, "_atr_snapshot_fresh", lambda *a, **k: False)
    monkeypatch.setattr(mon, "_atr_file_fresh", lambda p, *a, **k: p != str(results_path))
    monkeypatch.setattr(mon, "_atr_predictor_fresh", lambda *a, **k: True)

    writes = {}
    monkeypatch.setattr(
        mon, "_atomic_write_json", lambda path, data, indent=2: writes.__setitem__(path, data)
    )
    return atr_api, m, results_path, writes


def test_today_is_fetched_before_yesterday(monitor):
    atr_api, m, _, _ = monitor

    asyncio.run(m._refresh_atr_feeds({"events": {}}))

    assert atr_api.calls == ["today", "yesterday"]
    # One allowance funded the whole stale-feed burst (results only here).
    assert atr_api.bursts == [1]


def test_stealth_burst_funds_one_allowance_for_several_pages(monkeypatch, tmp_path):
    import time

    from core_agent.config import paths as cfg_paths

    monkeypatch.setattr(cfg_paths, "DATA_DIR", tmp_path)
    api = atr.AtTheRacesAPI()

    # No burst: the first call takes the allowance, the next is throttled.
    assert api._stealth_allowed() is True
    assert api._stealth_allowed() is False

    # A burst spends the same (already used) allowance for every stale page.
    api.open_stealth_burst(3)
    assert [api._stealth_allowed() for _ in range(3)] == [True, True, True]
    assert api._stealth_allowed() is False

    # The burst stamped the flag once, so the hour is still consumed.
    flag = tmp_path / ".atr_stealth_last"
    assert time.time() - float(flag.read_text().strip()) < 5


def test_yesterday_is_not_refetched_once_captured(monitor):
    """Captured *and watched to the end of its card* — then stop fetching it.

    Nov-2026: presence in the snapshot alone used to mean "finished", which is
    how 2026-11-10 froze at 12:20 with 8 of ~113 races and was never fetched
    again. A day is only droppable once the feed was still polling it after it
    ended (see test_atr_results_ratchet for the frozen-day regression).
    """
    atr_api, m, results_path, _ = monitor
    day = mon._atr_yesterday_iso()
    results_path.write_text(json.dumps({"results": [{
        "course": "Greyville",
        "date": day,
        "title": "1\n12:30 - Some Handicap",
        "runners": [{"name": "Alpha", "position": "1st"}],
    }], "timestamp": "2026-11-07T00:00:00"}))
    mon.ATR_RESULTS_CHECKS_PATH.write_text(json.dumps({
        "days": {day: {"last_checked_at": mon._atr_day_end_ts(day) + 60, "races_seen": 1}},
        "last_success": mon._atr_day_end_ts(day) + 60,
    }))

    asyncio.run(m._refresh_atr_feeds({"events": {}}))

    assert atr_api.calls == ["today"]


def test_merge_keeps_absolute_dates_and_dedupes():
    old = {"course": "Aintree", "date": OLDER_DAY, "title": "5\n17:00 - Hurdle",
           "runners": [{"name": "Old", "position": "1st"}]}
    fresh = {"course": "Aintree", "date": DAY, "title": "5\n17:00 - Hurdle",
             "runners": [{"name": "New", "position": "1st"}]}
    same_race_corrected = {"course": "Aintree", "date": DAY, "title": "5\n17:00 - Hurdle",
                           "runners": [{"name": "New", "position": "1st"}, {"name": "Second", "position": "2nd"}]}

    merged = mon._atr_merge_results([old], [fresh, same_race_corrected])

    dates = sorted(r["date"] for r in merged)
    assert dates == sorted([OLDER_DAY, DAY])
    corrected = next(r for r in merged if r["date"] == DAY)
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


# ── full-result pages (/racecard/…) ────────────────────────────────────────
# /results truncates at 1st–3rd (live Nov-2026). The per-race page carries the
# whole card; enrichment replaces summaries with it so 4th-place picks score.

def _full_page(entries, ran=8):
    rows = "".join(
        '<div class="card-entry">'
        f'<div class="card-cell card-cell--no-draw">{pos}</div>'
        f'<div class="card-cell card-cell--form">{dist}</div>'
        f'<div class="card-cell card-cell--horse card-cell--fill">{num}. {name} (GB)</div>'
        f'<div class="card-cell card-cell--odds">{odds}</div>'
        f'<div class="card-cell card-cell--stats">{age}</div>'
        "</div>"
        for pos, dist, num, name, odds, age in entries
    )
    filler = "<!-- " + ("x" * 12000) + " -->"
    return f"<html><body>{rows}{filler}</body></html>".encode()


def _article_linked(race_no, clock, horses, full="/racecard/Aintree/09-November-2026/1220"):
    rows = "".join(
        _runner(("1st", "2nd", "3rd")[i], name, odds)
        for i, (name, odds) in enumerate(horses)
    )
    return (
        '<article class="panel-content--medium">'
        f'<header><h3>{race_no}\n{clock} - Some Handicap '
        f'<a class="post-text__t" href="{full}">Full Result</a></h3></header>'
        f'<div class="list list--divided list--padded">{rows}</div>'
        "</article>"
    )


@needs_selector
def test_full_race_parser_reads_the_whole_card():
    html = _full_page([
        ("1", "", 6, "Lady Jetfire", "5/6", "5 11-2"),
        ("2", "7", 5, "Div Ine Glance", "14/1", "5 11-2"),
        ("3", "2½", 11, "Who's That Lady", "20/1", "4 11-2"),
        ("4", "9½", 1, "Afraidso", "16/1", "5 11-2"),
        ("5", "7½", 3, "Betsy Bluesky", "50/1", "4 11-2"),
        ("6", "nk", 8, "Lake Nagambie", "18/1", "4 11-2"),
        ("F", "", 7, "Lady Scarphia", "10/1", "5 11-2"),
        ("", "", 4, "Jackson Court", "Non Runner", "5 11-0"),
    ])
    runners = atr.AtTheRacesAPI._parse_full_race(html)

    assert len(runners) == 8
    by_name = {r["name"]: r for r in runners}
    assert by_name["Lady Jetfire"]["position"] == "1st"
    assert by_name["Lady Jetfire"]["number"] == 6
    assert by_name["Lady Jetfire"]["odds_decimal"] == 1.83
    assert by_name["Afraidso"]["position"] == "4th"
    assert by_name["Afraidso"]["distance_beaten"] == "9½"
    assert by_name["Lake Nagambie"]["position"] == "6th"
    assert by_name["Lady Scarphia"]["position"] == "F"
    assert by_name["Jackson Court"]["non_runner"] is True
    assert by_name["Jackson Court"]["position"] == ""


@needs_selector
def test_full_race_parser_rejects_unrun_cards():
    """A racecard for an upcoming race lists entries with no positions."""
    html = _full_page([("", "", 1, "Alpha", "5/1", "4 11-0")])
    assert atr.AtTheRacesAPI._parse_full_race(html) == []


@needs_selector
def test_enrichment_replaces_truncated_summary_and_caches(tmp_path, monkeypatch):
    from core_agent.config import paths
    monkeypatch.setattr(paths, "DATA_DIR", tmp_path, raising=False)
    monkeypatch.setattr(atr, "AtTheRacesAPI", atr.AtTheRacesAPI)
    import importlib
    importlib.reload(atr)  # DATA_DIR is read lazily; reload is unnecessary but harmless
    api = atr.AtTheRacesAPI()

    summary = _page(_meeting("Aintree", _article_linked(1, "12:20", [("Alpha", "5/2"), ("Bravo", "4/1"), ("Charlie", "8/1")])))
    full = _full_page([
        ("1", "", 1, "Alpha", "5/2", "4 11-2"),
        ("2", "2", 2, "Bravo", "4/1", "5 11-2"),
        ("3", "1½", 3, "Charlie", "8/1", "5 11-2"),
        ("4", "¾", 4, "Delta", "12/1", "6 11-2"),
        ("5", "3", 5, "Echo", "20/1", "4 11-2"),
        ("6", "5", 6, "Foxtrot", "25/1", "4 11-2"),
        ("7", "9", 7, "Golf", "33/1", "4 11-2"),
        ("8", "11", 8, "Hotel", "50/1", "4 11-2"),
    ])
    fetched = []

    def fake_fetch(path, allow_stealth=True):
        fetched.append(path)
        if str(path).startswith("/racecard/"):
            assert allow_stealth is False  # enrichment never burns the browser allowance
            return full
        return summary

    api._fetch = fake_fetch
    races = asyncio.run(api.get_results("today"))

    assert len(races) == 1
    race = races[0]
    assert race["full"] is True
    assert race["full_url"] == "/racecard/Aintree/09-November-2026/1220"
    assert [r["name"] for r in race["runners"]] == [
        "Alpha", "Bravo", "Charlie", "Delta", "Echo", "Foxtrot", "Golf", "Hotel",
    ]
    assert race["runners"][3]["position"] == "4th"  # the 4th the summary dropped
    assert len(fetched) == 2  # /results + one racecard page

    # Second pass: the disk cache serves the full card without another fetch.
    fetched.clear()
    api2 = atr.AtTheRacesAPI()
    api2._fetch = fake_fetch
    races2 = asyncio.run(api2.get_results("today"))
    assert races2[0]["runners"][3]["position"] == "4th"
    assert "/racecard/Aintree/09-November-2026/1220" not in fetched


@needs_selector
def test_enrichment_keeps_summary_when_full_fetch_fails():
    api = atr.AtTheRacesAPI()
    summary = _page(_meeting("Aintree", _article_linked(1, "12:20", [("Alpha", "5/2")])))
    api._fetch = lambda path, allow_stealth=True: summary

    races = asyncio.run(api.get_results("today"))

    assert len(races) == 1
    assert [r["name"] for r in races[0]["runners"]] == ["Alpha"]
    assert not races[0].get("full")


@needs_selector
def test_merge_keeps_the_fuller_record():
    full = {"course": "Aintree", "date": DAY, "title": "1\n12:20 - Hurdle",
            "runners": [{"name": f"H{i}", "position": f"{i}th"} for i in range(1, 9)]}
    summary = {"course": "Aintree", "date": DAY, "title": "1\n12:20 - Hurdle",
               "runners": [{"name": "H1", "position": "1st"}]}

    merged = mon._atr_merge_results([full], [summary])
    assert len(merged) == 1
    assert len(merged[0]["runners"]) == 8  # thin summary must not clobber the full card
