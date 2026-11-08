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
    # Meeting headers carry the off-time; the digits must not blank the venue.
    ("Aintree 13:50", "Aintree", "UK"),
    ("Hexham 13:00", "Hexham", "UK"),
    ("Fontwell 12:50", "Fontwell", "UK"),
    ("Dundalk 18:45", "Dundalk", "Ireland"),
    # Short codes seen on the movers feed resolve to real venues now.
    ("Ain", "Aintree", "UK"),
    ("Hex", "Hexham", "UK"),
    ("Fon", "Fontwell", "UK"),
    ("Dun", "Dundalk", "Ireland"),
    # Nov-2026: these three were the only courses left on the live movers
    # feed, and all three fell through to raw 3-letter codes, so the HUD
    # rendered "Course unverified — confirm on ATR" for every mover.
    ("Ffl", "Ffos Las", "UK"),
    ("Ffos Las", "Ffos Las", "UK"),
    ("Naa", "Naas", "Ireland"),
    ("Naas (IRE)", "Naas", "Ireland"),
    ("San", "Sandown", "UK"),
    ("Don", "Doncaster", "UK"),
    ("Kel", "Kelso", "UK"),
    ("Utt", "Uttoxeter", "UK"),
    ("Sou", "Southwell", "UK"),
    ("Gow", "Gowran Park", "Ireland"),
    ("G", "Greyville", "SA"),
    ("N", "Greyville Poly", "SA"),
    ("Y", "Flamingo Park (closed 2020)", "defunct"),
    ("Kimberley", "Flamingo Park (closed 2020)", "defunct"),
    # Validate-or-blank: page titles and horse headers must NEVER become venues
    ("MARKET MOVERS SUMMARY - UK & IRELAND | TUESDAY 6TH OCTOBER 2026", "", ""),
    ("(10) SHARK TWO ONE", "", ""),
    # ...but short tokens keep the OLD display behaviour (raw, not blank)
    ("SomeUnknownTrack", "SomeUnknownTrack", ""),
    ("Abc", "Abc", ""),
    ("", "", ""),
])
def test_normalize_course(raw, track, region):
    got = normalize_course(raw)
    assert got["track"] == track
    assert got["region"] == region


@pytest.mark.parametrize("raw", [
    # ATR's predictor/movers section headings, not venues. "Recent Winners"
    # claimed 26 of 49 predictions before the poison list covered it.
    "Recent Winners",
    "Today’s Top Horses",
    "Today’s Top Exactas",
    "Top 10 Steamers - Great Britain & Ireland",
    "Top 10 Drifters for Ffos Las",
])
def test_section_headings_are_never_venues(raw):
    """A wrong venue is worse than a blank one — always."""
    assert normalize_course(raw)["track"] == ""


def test_ambiguous_codes_never_guess():
    """"New" is Newcastle, Newmarket and Newbury — a guess labels the wrong
    meeting, so the code resolves to a blank venue instead."""
    assert normalize_course("New")["track"] == ""


@pytest.mark.parametrize("code,track", [
    ("Sco", "Scottsville"),
    ("Ken", "Kenilworth"),
    ("Tur", "Turffontein"),
    ("Vaa", "Vaal"),
])
def test_single_venue_prefixes_resolve(code, track):
    assert normalize_course(code)["track"] == track


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


def test_segment_by_headings_pairs_tables():
    """Regex fallback: tables inherit nearest preceding heading (raw)."""
    from core_agent.skills.parsers.attheraces_api import _segment_by_headings
    html = (b"<h2>Market Movers Summary - UK</h2>"
            b"<h3>Kempton</h3><table><tr><td>A</td></tr></table>"
            b"<h3>Southwell</h3><table><tr><td>B</td></tr></table>")
    seg = _segment_by_headings(html)
    assert len(seg) == 2
    assert seg[0][0] == "Kempton"
    assert seg[1][0] == "Southwell"
    assert "<table>" in seg[0][1]


# ── Nov-2026: movers/predictor shipped rows with no venue ──────────────────
#
# ATR serves /market-movers as TWO table shapes on the same page:
#   summary   Horse Name | Race | First Price | ▸ | Last Price | Mov | ATR Index
#   per-race  Horse Name | First Price | ▸ | Last Price | Mov | ATR Index | Swing
# plus a "Top 10 Steamers - Great Britain & Ireland" digest and a cookie table.
# The old parser assumed the summary shape and read fixed cell indexes, so
# every per-race row emitted current_odds ">" and an empty course — 196 of 266
# rows — and the HUD printed "Course unverified — confirm on ATR".

MOVERS_PAGE = b"""
<html><body>
<table><tr><td>Registers a unique ID to keep statistics of what videos
from YouTube the user has seen</td></tr></table>

<table>
  <caption>Top 10 Steamers - Great Britain &amp; Ireland</caption>
  <thead><tr><th>Horse Name</th><th>Race</th><th>First Price</th><th></th>
  <th>Last Price</th><th>Mov</th><th>ATR Index</th></tr></thead>
  <tbody>
    <tr><td>(1) Tap Tap Shamie</td><td>Ffl 12:50</td><td>7/4</td><td>&gt;</td>
        <td>10/11</td><td>48%</td><td>1535</td></tr>
    <tr><td>(4) Love Me Tender</td><td>Naa 13:00</td><td>10/11</td><td>&gt;</td>
        <td>4/6</td><td>26.37%</td><td>722</td></tr>
  </tbody>
</table>

<table>
  <caption><a href="/racecard/Ffos-Las/08-November-2026/1250">12:50 Blackmores
  Build Novices' Hurdle (GBB Race)</a></caption>
  <thead><tr><th>Horse Name</th><th>First Price</th><th></th><th>Last Price</th>
  <th>Mov</th><th>ATR Index</th><th>Graphical Swing</th></tr></thead>
  <tbody>
    <tr><td>(1) Tap Tap Shamie</td><td>7/4</td><td>&gt;</td><td>10/11</td>
        <td>48%</td><td>1535</td><td></td></tr>
    <tr><td>(4) Ink Black Heart</td><td>5/2</td><td>&gt;</td><td>11/4</td>
        <td>10%</td><td>171</td><td></td></tr>
  </tbody>
</table>

<table>
  <caption><a href="/racecard/Sandown/08-November-2026/1310">13:10
  Oddschecker Maiden Hurdle (GBB Race)</a></caption>
  <thead><tr><th>Horse Name</th><th>First Price</th><th></th><th>Last Price</th>
  <th>Mov</th><th>ATR Index</th><th>Graphical Swing</th></tr></thead>
  <tbody>
    <tr><td>(3) Kaylan</td><td>5/1</td><td>&gt;</td><td>7/2</td>
        <td>30%</td><td>900</td><td></td></tr>
  </tbody>
</table>
</body></html>
"""


def _movers(page=MOVERS_PAGE):
    from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI

    api = AtTheRacesAPI()
    api._fetch = lambda path: page
    import asyncio
    return asyncio.run(api.get_market_movers())


def test_movers_resolve_the_venue_for_every_row():
    pytest.importorskip("scrapling")
    rows = _movers()

    assert rows, "no movers parsed"
    assert all(r["course"] for r in rows), [r for r in rows if not r["course"]]
    assert {r["course"] for r in rows} == {"Ffos Las", "Naas", "Sandown"}
    assert {r["region"] for r in rows} == {"UK", "Ireland"}


def test_movers_read_the_real_price_columns():
    """current_odds is Last Price, first_show is First Price — not swapped."""
    pytest.importorskip("scrapling")
    by_horse = {r["horse"]: r for r in _movers()}

    shamie = by_horse["Tap Tap Shamie"]
    assert shamie["current_odds"] == "10/11"
    assert shamie["first_show"] == "7/4"
    assert shamie["movement"] == "48%"
    assert shamie["time"] == "12:50" and shamie["course"] == "Ffos Las"

    tender = by_horse["Love Me Tender"]
    assert (tender["current_odds"], tender["first_show"]) == ("4/6", "10/11")
    assert tender["course"] == "Naas" and tender["time"] == "13:00"


def test_movers_drop_rows_without_a_price():
    """A ">" arrow cell is layout, not a price; it must never become one."""
    pytest.importorskip("scrapling")
    rows = _movers()
    assert all(r["current_odds"] not in ("", ">") for r in rows)


def test_movers_strip_the_saddlecloth_prefix():
    """The HUD joins movers to live runners by name, so "(1) " has to go."""
    pytest.importorskip("scrapling")
    assert not any(r["horse"].startswith("(") for r in _movers())


def test_movers_dedupe_summary_against_per_race_tables():
    """Tap Tap Shamie appears in both shapes; the list must show her once."""
    pytest.importorskip("scrapling")
    horses = [r["horse"] for r in _movers()]
    assert len(horses) == len(set(horses))


PREDICTOR_PAGE = b"""
<html><body>
<input type="text" name="race-nav-datepicker" id="race-nav-datepicker"
       value="2026-11-08" readonly="readonly">

<table>
  <thead><tr><th>Race Details (Runners)</th><th>(Cloth) Horse Name (Forecast)</th>
  <th>Predictor / Result</th></tr></thead>
  <tbody>
    <tr><td>1 12:40 Sandown (6)
        <a href="/racecard/Sandown/08-November-2026/1240/predictor?showfix=yes">Sandown</a></td>
        <td>(5) Tune In A Box (3/1)</td>
        <td>Predictor Data Quality: 72.62% Percent Ahead: 24.67%</td></tr>
    <tr><td>6 15:37 Ffos Las (7)
        <a href="/racecard/Ffos-Las/08-November-2026/1537/predictor?showfix=yes">Ffos Las</a></td>
        <td>(2) Impatient (4/1)</td>
        <td>Predictor Data Quality: 75.07% Percent Ahead: 16.75%</td></tr>
  </tbody>
</table>

<table>
  <thead><tr><th>Race Details (Runners)</th><th>(Cloth) Horse Name (Forecast)</th>
  <th>Predictor / Result</th></tr></thead>
  <tbody>
    <tr><td>Sunday 8th Nov 2026</td></tr>
    <tr><td>Saturday 7th Nov 2026</td></tr>
    <tr><td>6 17:00 Southwell (9)
        <a href="/racecard/Southwell/07-November-2026/1700/predictor?showfix=yes">Southwell</a></td>
        <td>(1) Go On My Son (4/1)</td>
        <td>1st @ 4/6 Data Quality: 60.82%</td></tr>
  </tbody>
</table>
</body></html>
"""


def _predictions(page=PREDICTOR_PAGE):
    from core_agent.skills.parsers.attheraces_api import AtTheRacesAPI

    api = AtTheRacesAPI()
    api._fetch = lambda path: page
    import asyncio
    return asyncio.run(api.get_predictor())


def test_predictor_course_comes_from_the_racecard_link():
    """Not from the nearest <h3>: that filed 26 of 49 rows under "Recent Winners"."""
    pytest.importorskip("scrapling")
    rows = _predictions()

    assert [(r["course"], r["time"]) for r in rows] == [
        ("Sandown", "12:40"),
        ("Ffos Las", "15:37"),
    ]
    assert all(r["region"] == "UK" for r in rows)


def test_predictor_skips_yesterdays_digest():
    """The Recent Winners table shares the header but is a results digest."""
    pytest.importorskip("scrapling")
    rows = _predictions()

    assert "Recent Winners" not in {r["course"] for r in rows}
    assert "Southwell" not in {r["course"] for r in rows}
    assert {r["date"] for r in rows} == {"2026-11-08"}


def test_predictor_strips_cloth_and_odds_from_the_horse_name():
    pytest.importorskip("scrapling")
    assert [r["horse"] for r in _predictions()] == ["Tune In A Box", "Impatient"]


EXACTA_PAGE = b"""
<html><body>
<input type="text" name="race-nav-datepicker" id="race-nav-datepicker"
       value="2026-11-08" readonly="readonly">

<table>
  <thead><tr><th>Race Details (Runners)</th><th>(Cloth) Horse Name (Forecast)</th>
  <th>Predictor / Result</th></tr></thead>
  <tbody>
    <tr><td>6 15:37 Ffos Las (7)
        <a href="/racecard/Ffos-Las/08-November-2026/1537/predictor?showfix=yes">Ffos Las</a></td>
        <td>(2)
            Impatient
            (4/1)
            (4)
            Galway Reel
            (15/8)</td>
        <td>Predictor</td></tr>
  </tbody>
</table>
</body></html>
"""


def test_predictor_exacta_pair_stays_one_readable_row():
    """ATR files both exacta legs in one cell; the pair is the prediction.

    Read as a single name it surfaced in the HUD as
    "Impatient (4/1) (4) Galway Reel" (Nov-2026). It must not become two picks
    either — ATR never tipped them individually.
    """
    pytest.importorskip("scrapling")
    rows = _predictions(EXACTA_PAGE)

    assert len(rows) == 1
    assert rows[0]["horse"] == "Impatient / Galway Reel"
    assert rows[0]["type"] == "exacta"
    assert rows[0]["course"] == "Ffos Las"


def test_predictor_single_runner_rows_are_typed_single():
    pytest.importorskip("scrapling")
    assert {r["type"] for r in _predictions()} == {"single"}


def test_split_runner_cell_handles_the_shapes_atr_ships():
    from core_agent.skills.parsers.attheraces_api import _split_runner_cell

    assert _split_runner_cell("(5)\nTune In A Box\n(3/1)") == ["Tune In A Box"]
    assert _split_runner_cell("(5) Tune In A Box (3/1)") == ["Tune In A Box"]
    assert _split_runner_cell("(2)Impatient(4/1)(4)Galway Reel(15/8)") == [
        "Impatient",
        "Galway Reel",
    ]
    assert _split_runner_cell("") == []


