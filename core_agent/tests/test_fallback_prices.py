"""Fallback price sources must actually reach the card (2026-11-25).

Three separate failures let a fully-priced card publish as 127 races with zero
prices:

1. The gap merges ran *before* ``_apply_betfair_spine``, so races the spine
   created were never hydrated.
2. SportyBet's ``Date!`` scalar needs RFC3339, but it was sent ``YYYY-MM-DD``;
   Apollo's parse error was swallowed into an empty list.
3. SportyBet's price rows are named ``racingFutureWin``, not ``WIN``.

These tests pin all three, plus the pool-entry guard and the swarm loop's
news-first ordering.
"""

import asyncio
import json
import time
from unittest.mock import patch

import pytest

from core_agent.core.adaptive_odds_monitor import (
    _apply_fallback_merges,
    _merge_sportybet_into,
)
from core_agent.skills.parsers.soccershop_api import SoccerShopAPI
from core_agent.skills.parsers.sportybet_api import SportyBetAPI, normalize_sportybet_odds


# --- 1. merges run after the spine -----------------------------------------

def _spine_race(course="Kenilworth", num=3, odds=None):
    return {
        "course": course,
        "raceNumber": num,
        "runners": [
            {"name": "Silver Chord", "odds": odds},
            {"name": "Winter Palace", "odds": odds},
        ],
    }


def _book_snapshot(course="Kenilworth", num=3, odds=4.5):
    return {
        "events": {
            "x": {
                "course": course,
                "raceNumber": num,
                "runners": [
                    {"name": "Silver Chord", "odds": odds},
                    {"name": "Winter Palace", "odds": odds + 1},
                ],
            }
        }
    }


def test_sportybet_hydrates_races_the_spine_created():
    state = {"events": {"bf:1": _spine_race()}}
    _merge_sportybet_into(state, _book_snapshot())

    odds = [r["odds"] for r in state["events"]["bf:1"]["runners"]]
    assert odds == [4.5, 5.5]
    assert all(r["price_source"] == "sportybet"
               for r in state["events"]["bf:1"]["runners"])


def test_sportybet_never_overwrites_a_real_price():
    state = {"events": {"bf:1": _spine_race(odds=2.4)}}
    _merge_sportybet_into(state, _book_snapshot(odds=9.9))

    assert [r["odds"] for r in state["events"]["bf:1"]["runners"]] == [2.4, 2.4]


def test_sportybet_matches_on_course_and_race_number_not_just_course():
    """A different race at the same track must not inherit these prices."""
    state = {"events": {"bf:1": _spine_race(num=7)}}
    _merge_sportybet_into(state, _book_snapshot(num=3))

    assert [r["odds"] for r in state["events"]["bf:1"]["runners"]] == [None, None]


def test_fallback_merges_fill_form_and_prices_together():
    state = {"events": {"bf:1": _spine_race()}}
    bf = {"events": {"m1": {"course": "Kenilworth", "raceNumber": 3,
                            "runners": [{"name": "Silver Chord", "gear": "b"}]}}}

    _apply_fallback_merges(state, bf, {"events": {}}, _book_snapshot())

    runners = state["events"]["bf:1"]["runners"]
    assert runners[0]["odds"] == 4.5
    assert runners[1]["odds"] == 5.5


# --- 2. SportyBet date format ---------------------------------------------

def test_bare_date_is_coerced_to_rfc3339():
    assert SportyBetAPI._rfc3339("2026-11-25") == "2026-11-25T00:00:00Z"
    assert SportyBetAPI._rfc3339("2026-11-25", end_of_day=True) == "2026-11-25T23:59:59Z"


def test_existing_timestamp_is_left_alone():
    stamp = "2026-11-25T05:00:00.000Z"
    assert SportyBetAPI._rfc3339(stamp) == stamp


def test_meetings_query_sends_rfc3339(monkeypatch):
    captured = {}

    def fake_query(q, variables, root):
        captured.update(variables)
        return {"data": {"meetingsBetween": []}}

    api = SportyBetAPI()
    monkeypatch.setattr(api, "_query", fake_query)
    api.fetch_meetings_sync("2026-11-25", "2026-11-25")

    assert captured["startDate"] == "2026-11-25T00:00:00Z"
    assert captured["endDate"] == "2026-11-25T23:59:59Z"


# --- 3. SportyBet price row naming ----------------------------------------

def test_decimal_prices_pass_through_untouched():
    assert normalize_sportybet_odds(9.5) == 9.5
    assert normalize_sportybet_odds(1.01) == 1.01
    assert normalize_sportybet_odds(None) == "SP"
    assert normalize_sportybet_odds(0.9) == "SP"


# --- 4. SoccerShop hygiene ------------------------------------------------

def test_pool_entries_are_not_races():
    for name in ("Bipot - 1", "Pick 6", "Jackpot Leg 2", "Swinger 3"):
        assert SoccerShopAPI._is_pool_entry({"meetingCode": name}) is True


def test_real_meetings_are_kept():
    for name in ("Kenilworth", "Turffontein Inside", "Gulfstream Park"):
        assert SoccerShopAPI._is_pool_entry({"meetingCode": name}) is False


def test_soccershop_defaults_to_all_countries():
    """ZA-only discarded 11 of 14 usable events on a Betway-blocked day."""
    import inspect

    for fn in (SoccerShopAPI.fetch_racing_data, SoccerShopAPI.get_snapshot_format):
        sig = inspect.signature(fn)
        assert sig.parameters["country_code"].default is None


# --- 5. swarm loop ordering -----------------------------------------------

def test_news_is_polled_even_when_backfill_hangs(monkeypatch):
    """The old order let a hung backfill starve news for 32 hours."""
    import core_agent.skills.swarm_researcher as sr

    called = []

    async def fake_poll_news():
        called.append("news")
        return 0

    async def hanging_backfill(_snap):
        called.append("backfill")
        await asyncio.sleep(3600)

    def fake_snapshot():
        return {"events": {"x": {}}}

    monkeypatch.setattr(sr, "poll_news", fake_poll_news)
    monkeypatch.setattr(sr, "backfill_form_insights", hanging_backfill)
    monkeypatch.setattr(sr, "BACKFILL_TIMEOUT_SECONDS", 0.05)
    monkeypatch.setitem(
        __import__("sys").modules,
        "core_agent.core.snapshot_cache",
        type("M", (), {"get_snapshot": staticmethod(fake_snapshot)}),
    )

    async def run_one_cycle():
        task = asyncio.create_task(sr.run_swarm_loop(interval=0.01))
        await asyncio.sleep(0.3)
        task.cancel()

    asyncio.run(run_one_cycle())

    assert called.count("news") >= 2


# --- 6. SportyBet window cap and transport (found 2026-11-25) --------------
#
# Three more silent failures, each of which alone produced "0 meetings":
#   * the 48h window (now-12h .. now+36h) exceeds a documented 32h cap
#   * GraphQL errors arrive with HTTP 200 and were dropped on the floor
#   * a throttled batch ("not authorized") discarded a whole chunk

def _fake_urlopen(body):
    """Minimal stand-in for urllib.request.urlopen returning ``body`` as JSON."""

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(body).encode("utf-8")

    return lambda request, timeout=None: _Response()


def test_query_window_never_exceeds_the_32h_cap():
    """The API rejects wider windows: 'duration ... cannot be more than 32h0m0s'."""
    from datetime import datetime

    start, end = SportyBetAPI._query_window()
    a = datetime.strptime(start, "%Y-%m-%dT%H:%M:%SZ")
    b = datetime.strptime(end, "%Y-%m-%dT%H:%M:%SZ")
    assert (b - a).total_seconds() <= SportyBetAPI.MAX_WINDOW_HOURS * 3600


def test_query_window_uses_a_full_calendar_day_when_given_a_date():
    assert SportyBetAPI._query_window("2026-11-25") == (
        "2026-11-25T00:00:00Z",
        "2026-11-25T23:59:59Z",
    )


def test_graphql_errors_are_logged_not_swallowed(caplog):
    """HTTP 200 + {"errors": [...]} used to look exactly like an empty race day."""
    import logging

    body = {"errors": [{"message": "not authorized to perform this action"}]}
    with patch(
        "core_agent.skills.parsers.sportybet_api.urllib.request.urlopen",
        _fake_urlopen(body),
    ), caplog.at_level(logging.WARNING):
        SportyBetAPI()._query("query { x }", {}, "raceCard")

    assert "not authorized" in caplog.text


def test_throttled_batch_is_retried_and_does_not_lose_the_chunk(monkeypatch):
    api = SportyBetAPI()
    calls = {"n": 0}

    def flaky_query(q, variables, root):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"errors": [{"message": "not authorized to perform this action"}]}
        return {
            "data": {
                "meetingRaces": [
                    {"name": "Kenilworth", "track": {"name": "Kenilworth"},
                     "races": [{"id": "r1", "number": 1, "runners": []}]}
                ]
            }
        }

    monkeypatch.setattr(api, "_query", flaky_query)
    monkeypatch.setattr(api, "RETRY_BACKOFF_SECONDS", 0)
    cards = api.fetch_race_cards_sync(["r1"])

    assert calls["n"] == 2
    assert len(cards) == 1


def test_transport_is_stdlib_urllib_not_curl_cffi():
    """curl_cffi/httpx get HTTP 403 here; urllib gets HTTP 200. Do not revert."""
    import core_agent.skills.parsers.sportybet_api as mod

    assert not hasattr(mod, "requests")
    assert "curl_cffi" not in dir(mod)


# --- 7. fallback fetch rate limiting --------------------------------------
@pytest.fixture(autouse=True)
def _isolate_fallback_cache(tmp_path, monkeypatch):
    """Never let these tests read or write the real volume cache."""
    import core_agent.core.adaptive_odds_monitor as mon

    mon._FALLBACK_CACHE.clear()
    monkeypatch.setattr(
        mon,
        "_fallback_disk_path",
        lambda name: str(tmp_path / f"fallback_{name}_latest.json"),
    )


#
# The monitor sleeps only 15s while races are live; uncached, SportyBet's 13
# batched calls would run ~52 times/minute and get us throttled.

def test_fallback_fetch_is_cached_within_ttl():
    import core_agent.core.adaptive_odds_monitor as mon

    calls = []

    async def factory():
        calls.append(1)
        return {
            "events": {"a": {"runners": [{"name": "Horse", "odds": 4.5}]}},
            "count": 1,
        }

    mon._FALLBACK_CACHE.clear()
    asyncio.run(mon._cached_fallback("sportybet", factory))
    asyncio.run(mon._cached_fallback("sportybet", factory))

    assert len(calls) == 1


def test_failed_refresh_keeps_the_last_good_snapshot():
    import core_agent.core.adaptive_odds_monitor as mon

    mon._FALLBACK_CACHE.clear()
    mon._FALLBACK_CACHE["sportybet"] = (
        time.time() - 130,  # past TTL but inside the 3h stale cap
        {
            "events": {"a": {"runners": [{"name": "Horse", "odds": 4.5}]}},
            "count": 1,
        },
    )

    async def failing():
        raise RuntimeError("throttled")

    result = asyncio.run(mon._cached_fallback("sportybet", failing))
    assert result["count"] == 1


def test_stale_fallback_data_is_discarded_not_published_forever():
    import core_agent.core.adaptive_odds_monitor as mon

    mon._FALLBACK_CACHE.clear()
    mon._FALLBACK_CACHE["sportybet"] = (
        time.time() - mon.FALLBACK_MAX_STALE_SECS - 60,
        {
            "events": {"stale": {"runners": [{"name": "Old", "odds": 3.0}]}},
            "count": 1,
        },
    )

    async def empty():
        return {"events": {}, "count": 0}

    result = asyncio.run(mon._cached_fallback("sportybet", empty))
    assert result["events"] == {}



def test_unpriced_snapshot_does_not_evict_the_last_good_price_table():
    """The alternating priced/unpriced card every 5 minutes came from here."""
    import core_agent.core.adaptive_odds_monitor as mon

    good = {
        "events": {"a": {"runners": [{"name": "Horse", "odds": 4.5}]}},
        "count": 1,
    }
    mon._FALLBACK_CACHE.clear()
    mon._FALLBACK_CACHE["sportybet"] = (time.time() - 130, good)

    async def half_blocked():
        return {
            "events": {"a": {"runners": [{"name": "Horse", "odds": "SP"}]}},
            "count": 1,
        }

    result = asyncio.run(mon._cached_fallback("sportybet", half_blocked))
    assert result is good


def test_fallback_price_table_survives_a_fresh_modal_container():
    """Modal runs each cron tick in a new process — memory alone is not enough."""
    import core_agent.core.adaptive_odds_monitor as mon

    good = {
        "events": {"a": {"runners": [{"name": "Horse", "odds": 6.5}]}},
        "count": 1,
    }

    async def good_fetch():
        return good

    asyncio.run(mon._cached_fallback("sportybet", good_fetch))
    mon._FALLBACK_CACHE.clear()  # simulate a fresh container

    async def blocked():
        raise RuntimeError("HTTP 403")

    assert asyncio.run(mon._cached_fallback("sportybet", blocked)) == good


# --- 8. news starvation from a numeric age -------------------------------
def test_numeric_age_does_not_kill_the_news_poll(monkeypatch):
    """One int age raised AttributeError and froze news for 34 hours."""
    import core_agent.skills.swarm_researcher as sr

    insight = sr.build_field_insight({"name": "Horse", "age": 5, "weight": 54})
    assert isinstance(insight, str)

    async def boom(_state):
        raise RuntimeError("bad runner")

    monkeypatch.setattr(sr, "_backfill_form_insights_impl", boom)
    assert asyncio.run(sr.backfill_form_insights({"events": {}})) == 0


# --- 9. descriptive fields from the fallback books -----------------------
def test_missing_jockey_trainer_and_draw_are_filled_from_fallback():
    state = {"events": {"bf:1": _spine_race()}}
    sb = {
        "events": {
            "x": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [
                    {
                        "name": "Silver Chord",
                        "odds": 4.5,
                        "jockeyName": "C Zackey",
                        "trainerName": "D Kannemeyer",
                        "draw": 7,
                        "timeForm": "Won last time at this track.",
                    },
                    {"name": "Winter Palace", "odds": 5.5},
                ],
            }
        }
    }
    _merge_sportybet_into(state, sb)

    r = state["events"]["bf:1"]["runners"][0]
    assert r["jockeyName"] == "C Zackey"
    assert r["trainerName"] == "D Kannemeyer"
    assert r["draw"] == 7
    assert r["timeForm"].startswith("Won last time")


def test_real_descriptive_fields_are_never_overwritten():
    state = {
        "events": {
            "bf:1": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [
                    {
                        "name": "Silver Chord",
                        "odds": 2.4,
                        "jockeyName": "Real Jockey",
                        "draw": 3,
                    }
                ],
            }
        }
    }
    sb = {
        "events": {
            "x": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [
                    {
                        "name": "Silver Chord",
                        "odds": 9.9,
                        "jockeyName": "Other Jockey",
                        "draw": 12,
                    }
                ],
            }
        }
    }
    _merge_sportybet_into(state, sb)

    r = state["events"]["bf:1"]["runners"][0]
    assert r["jockeyName"] == "Real Jockey"
    assert r["draw"] == 3
    assert r["odds"] == 2.4


def test_betfair_trainer_key_is_surfaced_as_trainername():
    from core_agent.core.adaptive_odds_monitor import _apply_fallback_merges

    state = {
        "events": {
            "bf:1": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [{"name": "Horse", "odds": "SP", "trainer": "J Crawford"}],
            }
        }
    }
    _apply_fallback_merges(state, {"events": {}}, {"events": {}}, {"events": {}})
    assert state["events"]["bf:1"]["runners"][0]["trainerName"] == "J Crawford"


# --- 10. Hong Kong spine --------------------------------------------------
def test_hong_kong_meetings_are_added_only_when_missing():
    from core_agent.core.adaptive_odds_monitor import _apply_sportybet_spine

    hk = {
        "events": {
            "sportybet_hk1": {
                "course": "Happy Valley",
                "en": "HKG: Happy Valley",
                "raceNumber": 1,
                "t": "10:40",
                "runners": [{"name": "Horse", "odds": 3.2}],
            }
        }
    }
    state = {"events": {}}
    assert _apply_sportybet_spine(state, hk) == 1
    assert "sportybet_hk1" in state["events"]
    assert _apply_sportybet_spine(state, hk) == 0


def test_non_hk_meetings_are_not_added_to_the_card():
    from core_agent.core.adaptive_odds_monitor import _apply_sportybet_spine

    state = {"events": {}}
    sb = {
        "events": {
            "sportybet_aus": {
                "course": "Wyong",
                "raceNumber": 1,
                "runners": [{"name": "Horse", "odds": 3.2}],
            }
        }
    }
    assert _apply_sportybet_spine(state, sb) == 0


def test_betway_form_and_ratings_win_when_betway_returns():
    """Fallbacks are gap-fillers only: a real Betway value is never replaced."""
    state = {
        "events": {
            "bw:9": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [
                    {
                        "name": "Silver Chord",
                        "odds": 4.5,
                        "jockeyName": "Betway Jockey",
                        "trainerName": "Betway Trainer",
                        "draw": 2,
                        "timeForm": "Betway's own form comment",
                        "official_rating": 96,
                    }
                ],
            }
        }
    }
    sb = {
        "events": {
            "x": {
                "course": "Kenilworth",
                "raceNumber": 3,
                "runners": [
                    {
                        "name": "Silver Chord",
                        "odds": 2.0,
                        "jockeyName": "Other Jockey",
                        "trainerName": "Other Trainer",
                        "draw": 13,
                        "timeForm": "Other book's form comment",
                    }
                ],
            }
        }
    }
    _merge_sportybet_into(state, sb)

    r = state["events"]["bw:9"]["runners"][0]
    assert r["odds"] == 4.5
    assert r["jockeyName"] == "Betway Jockey"
    assert r["trainerName"] == "Betway Trainer"
    assert r["draw"] == 2
    assert r["timeForm"] == "Betway's own form comment"
    assert r["official_rating"] == 96
