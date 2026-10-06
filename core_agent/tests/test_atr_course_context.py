"""ATR course context: normalize_course map, meeting-table iteration,
snapshot backfill, Betway international schedule parsing.

No network, no creds — fixture HTML + fakes.
"""
import pytest

from core_agent.skills.parsers.attheraces_api import normalize_course
from core_agent.skills.parsers.atr_enrich import (
    attach_snapshot_context,
    build_runner_index,
)


@pytest.mark.parametrize("raw,track,region", [
    ("Newcastle Results", "Newcastle", "UK"),
    ("Ntt 13:23", "Nottingham", "UK"),
    ("G", "Greyville", "SA"),
    ("N", "Greyville Poly", "SA"),
    ("Y", "Flamingo Park (closed 2020)", "defunct"),
    ("Kimberley", "Flamingo Park (closed 2020)", "defunct"),
    # Validate-or-blank: page titles and horse headers must NEVER become venues
    ("SomeUnknownTrack", "", ""),
    ("MARKET MOVERS SUMMARY - UK & IRELAND | TUESDAY 6TH OCTOBER 2026", "", ""),
    ("(10) SHARK TWO ONE", "", ""),
    ("", "", ""),
])
def test_normalize_course(raw, track, region):
    got = normalize_course(raw)
    assert got["track"] == track
    assert got["region"] == region


def test_defunct_never_resolves_live():
    got = normalize_course("Y")
    assert "closed" in got["track"]
    assert got["region"] != "SA"


def test_runner_index_and_backfill():
    events = {
        "e1": {"course": "Greyville", "start_time": "19:35",
               "runners": [{"name": "Arverni Princess", "outcomeName": "12.0"}]},
    }
    idx = build_runner_index(events)
    assert idx["arverniprincess"]["course"] == "Greyville"

    entries = [
        {"horse": "Arverni Princess", "course": "", "time": ""},      # blank -> filled
        {"horse": "Arverni Princess", "course": "NTT", "time": "1"},   # ATR wins, untouched
        {"horse": "Nobody", "course": "", "time": ""},                 # no match, stays blank
    ]
    out = attach_snapshot_context(entries, events)
    assert out[0]["course"] == "Greyville" and out[0]["time"] == "19:35"
    assert out[1]["course"] == "NTT"
    assert out[2]["course"] == ""


def test_backfill_no_snapshot_noop():
    entries = [{"horse": "X", "course": "", "time": ""}]
    assert attach_snapshot_context(entries, {}) == entries
    assert attach_snapshot_context([], {"e": {}}) == []


POISONED_PAGE = b"""
<html><body>
<h2>MARKET MOVERS SUMMARY - UK &amp; IRELAND | TUESDAY 6TH OCTOBER 2026</h2>
<div class="push--x-small">
<a class="panel-header"><h2>Kempton Results</h2></a>
<table><tr><th>Horse</th><th>Race</th><th>Last</th></tr>
<tr><td>Speedy</td><td>Kmp 14:20</td><td>5/2</td><td>7/2</td><td>30%</td></tr></table>
</div>
<h3>(10) SHARK TWO ONE 19:00</h3>
<table><tr><th>Horse</th><th>Race</th><th>Last</th></tr>
<tr><td>Affettuoso</td><td></td><td>5/2</td></tr></table>
</body></html>
"""


def test_meeting_tables_ignore_page_headings():
    """Regression: page title and horse headers must not become courses."""
    pytest.importorskip("scrapling")
    from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI, Selector
    api = AtTheRacesAPI()
    sel = Selector(POISONED_PAGE, auto_save=True, adaptive=True)
    groups = api._iter_meeting_tables(sel)
    titles = [t for t, _ in groups]
    assert "Kempton" in titles
    assert not any("MARKET MOVERS" in t for t in titles)
    assert not any("SHARK TWO ONE" in t for t in titles)


@pytest.mark.asyncio
async def test_international_schedule_from_betway_shape():
    """Dead TAB URL replaced: Betway GetDaily regions/leagues parse, loud failures."""
    from core_agent.skills.race_schedule import RaceScheduleService

    class FakeResp:
        status_code = 200

        def json(self):
            return {"regions": [
                {"name": "UK and Ireland",
                 "sportEvents": [{"eventId": 1, "league": "Newcastle", "isFinished": False}]},
                {"name": "South Africa",
                 "sportEvents": [{"eventId": 2, "league": "Vaal", "isFinished": False}]},
                {"name": "Hong Kong",
                 "sportEvents": [{"eventId": 3, "league": "Happy Valley", "isFinished": True}]},
            ]}

    class FakeClient:
        async def get(self, url, headers=None):
            assert "GetDaily" in url
            return FakeResp()

    import core_agent.core.http_client as http_client
    orig = getattr(http_client, "get_async_client", None)
    http_client.get_async_client = lambda timeout=15.0, resolve_hosts=None: FakeClient()
    try:
        svc = RaceScheduleService()
        tracks = await svc._fetch_international_schedule("2026-10-04")
    finally:
        if orig is not None:
            http_client.get_async_client = orig
        else:
            delattr(http_client, "get_async_client")
    # Newcastle (live) + happy_valley excluded (finished) + SA excluded
    assert "newcastle" in tracks
    assert tracks["newcastle"]["region"] == "UK and Ireland"
    assert "happy_valley" not in tracks
    assert "vaal" not in tracks
