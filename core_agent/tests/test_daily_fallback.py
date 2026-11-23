"""GetDaily-first card when GetEvent is WAF-refused (2026-11-23).

Chrome DevTools on the live Betway site confirmed the endpoints and query
strings are unchanged; GetDaily now carries ``raceEventDetails.racers`` for
every race (157 events / 1,410 runners observed), while only GetEvent carries
prices. GetDaily answers from Modal's Azure IP; GetEvent does not. So a refused
GetEvent must cost a race its *prices*, never its place on the card.
"""

import asyncio
import time

from core_agent.skills.parsers.betway_api import BetwayAPI, _details_from_daily

ALLOWED = ["South Africa", "UK and Ireland", "USA", "Japan"]


def _daily_event(eid, *, finished=False, racers=True, league="Bangor-on-Dee"):
    return {
        "eventId": eid,
        "isFinished": finished,
        "league": league,
        "name": "12:05 " + league,
        "expectedStartEpoch": int(time.time()) + 3600,
        "sportSpecificProperties": {"raceNumber": "3"},
        "raceEventDetails": {
            "eventId": eid,
            "racers": [
                {
                    "outcomeIds": [eid * 10 + 1],
                    "outcomeName": "Starmount",
                    "number": "4",
                    "jockeyName": "Ben Jones",
                    "trainerName": "B Pauling",
                    "form": "F1/141P-",
                    "weight": "11st 5lbs",
                },
                {
                    "outcomeIds": [eid * 10 + 2],
                    "outcomeName": "Count Of Vendome",
                    "number": "1",
                    "jockeyName": "B S Hughes",
                    "trainerName": "D McCain Jnr",
                },
            ]
            if racers
            else []
        },
    }


def _daily(*events, region="UK and Ireland"):
    return {"regions": [{"name": region, "sportEvents": list(events)}]}


def test_daily_details_cover_races_getevent_refused():
    data = _daily(_daily_event(101), _daily_event(102))
    details = _details_from_daily(data, have_ids={101}, allowed_regions=ALLOWED)
    assert [d["eventId"] for d in details] == [102]
    d = details[0]
    assert d["price_source"] == "daily"
    assert d["regionName"] == "UK and Ireland"
    assert d["leagueName"] == "Bangor-on-Dee"
    assert d["result"]["prices"] == []
    assert d["result"]["events"][0]["raceEventDetails"]["racers"]


def test_finished_races_are_skipped_but_fieldless_keep_their_slot():
    data = _daily(
        _daily_event(201, finished=True),
        _daily_event(202, racers=False),
        _daily_event(203),
    )
    details = _details_from_daily(data, have_ids=set(), allowed_regions=ALLOWED)
    assert [d["eventId"] for d in details] == [202, 203]
    assert details[0]["field_pending"] is True
    assert details[1]["field_pending"] is False


def test_fieldless_race_still_appears_on_the_card():
    """US meetings publish fields late — the race must not vanish meanwhile."""
    api = BetwayAPI()
    details = _details_from_daily(_daily(_daily_event(601, racers=False)), set(), ALLOWED)

    async def fake_fetch():
        return {"status": "success", "details": details, "daily_unpriced": 1}

    api.fetch_racing_data = fake_fetch  # type: ignore[method-assign]
    snap = asyncio.run(api.get_snapshot_format())
    ev = snap["events"]["601"]
    assert ev["runners"] == []
    assert ev["field_pending"] is True
    assert ev["raceNumber"] == 3


def test_disallowed_regions_are_not_admitted():
    data = _daily(_daily_event(301), region="Mauritius")
    assert _details_from_daily(data, set(), ALLOWED) == []


def test_snapshot_from_daily_only_details_is_unpriced_but_complete():
    api = BetwayAPI()
    details = _details_from_daily(_daily(_daily_event(401), _daily_event(402)), set(), ALLOWED)

    async def fake_fetch():
        return {"status": "success", "details": details, "daily_unpriced": len(details)}

    api.fetch_racing_data = fake_fetch  # type: ignore[method-assign]
    snap = asyncio.run(api.get_snapshot_format())

    assert snap["fetch_ok"] is True
    assert snap["count"] == 2
    assert snap["daily_unpriced"] == 2
    ev = snap["events"]["401"]
    assert ev["price_source"] == "daily"
    assert ev["course"] == "Bangor-on-Dee"
    assert ev["raceNumber"] == 3
    assert [r["name"] for r in ev["runners"]] == ["Starmount", "Count Of Vendome"]
    assert all(r["odds"] == "SP" for r in ev["runners"])
    assert ev["runners"][0]["jockeyName"] == "Ben Jones"


def test_priced_event_details_keep_their_price_source():
    api = BetwayAPI()
    event = _daily_event(501)
    detail = {
        "eventId": 501,
        "regionName": "UK and Ireland",
        "leagueName": "Bangor-on-Dee",
        "result": {
            "events": [event],
            "markets": [{"marketId": "9", "name": "Race Winner"}],
            "outcomes": [
                {"outcomeId": str(501 * 10 + 1), "marketId": "9", "outcomeName": "Starmount"},
            ],
            "prices": [{"outcomeId": str(501 * 10 + 1), "priceDecimal": 4.5}],
        },
    }

    async def fake_fetch():
        return {"status": "success", "details": [detail]}

    api.fetch_racing_data = fake_fetch  # type: ignore[method-assign]
    snap = asyncio.run(api.get_snapshot_format())
    ev = snap["events"]["501"]
    assert ev["price_source"] == "event"
    priced = {r["name"]: r["odds"] for r in ev["runners"]}
    assert priced["Starmount"] == 4.5
    assert priced["Count Of Vendome"] == "SP"
