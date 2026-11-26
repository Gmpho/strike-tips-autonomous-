"""Prices must survive a blocked cycle (26 Nov 2026).

Betway's Cloudflare refuses Modal's egress for hours at a time while GetDaily
still supplies the race list. Two separate mechanisms then stripped a fully
priced card:

1. the 15-minute ``scheduler_scan`` ran *later* than the monitor, so the old
   timestamp-only guard let it overwrite a 436-price card with a 12-price one;
2. an event present in both cards but unpriced this cycle was treated as an
   update, so the id-based carry-forward never restored its prices.

Pinned here:

- a fresh monitor card is authoritative over scan writers for 30 minutes;
- ``carry_forward_prices`` restores prices/form per runner, never overwriting a
  live value and never touching non-runners;
- ``betway_prices_last_good.json`` rehydrates unpriced races, keeps real prices,
  and drops entries after the TTL.
"""

import json
import time
from datetime import datetime, timedelta

import pytest

from core_agent.core import snapshot_writer
from core_agent.skills.parsers import betway_api


@pytest.fixture(autouse=True)
def _isolated_race_registry(tmp_path, monkeypatch):
    """Never read/write the shared on-disk race registry."""
    monkeypatch.setattr(snapshot_writer, "RACE_REGISTRY_PATH", tmp_path / "registry.json")


def _future_hhmm(minutes=90):
    return (datetime.now() + timedelta(minutes=minutes)).strftime("%H:%M")


def _snapshot(events, source=None):
    out = {"events": events}
    if source:
        out["snapshot_source"] = source
    return out


def _race(runners, course="Vaal", number=1):
    return {"en": course, "course": course, "raceNumber": number,
            "t": _future_hhmm(), "runners": runners}


# ── 1. Monitor card is authoritative over scan writers ──────────────────────


def test_scan_write_skipped_while_monitor_card_is_fresh(tmp_path, monkeypatch):
    """A later-running scan must not clobber a fresh, priced monitor card."""
    path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", path)

    snapshot_writer.write_market_snapshot(
        _snapshot({"m1": _race([{"name": "A", "odds": 4.5}])}, "monitor"),
        source="monitor",
        path=path,
    )
    before = path.read_text()

    out = snapshot_writer.write_market_snapshot(
        _snapshot({"s1": _race([{"name": "B", "odds": "SP"}], number=2)}),
        source="scheduler_scan",
        path=path,
    )

    assert path.read_text() == before, "scan must not touch a fresh monitor file"
    # The scan still gets the monitor's races for its own in-memory use.
    assert {"m1", "s1"} <= set(out["events"])


def test_scan_write_takes_over_once_monitor_card_ages_out(tmp_path, monkeypatch):
    """A dead monitor cannot freeze the card forever."""
    path = tmp_path / "market_snapshot_latest.json"
    monkeypatch.setattr(snapshot_writer, "MARKET_SNAPSHOT_PATH", path)
    path.write_text(json.dumps({
        "events": {"m1": _race([{"name": "A", "odds": 4.5}])},
        "snapshot_source": "monitor",
        "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
    }))

    snapshot_writer.write_market_snapshot(
        _snapshot({"s1": _race([{"name": "B", "odds": 2.1}], number=2)}),
        source="scheduler_scan",
        path=path,
    )

    current = json.loads(path.read_text())
    assert current["snapshot_source"] == "scheduler_scan"
    assert {"m1", "s1"} <= set(current["events"])


# ── 2. Per-runner price carry-forward ───────────────────────────────────────


def _write_previous(tmp_path, events):
    path = tmp_path / "market_snapshot_latest.json"
    path.write_text(json.dumps({"events": events}))
    return path


def test_carry_forward_restores_price_and_form(tmp_path):
    """The exact 26 Nov case: same event id, every runner back to SP."""
    path = _write_previous(tmp_path, {
        "e1": _race([{
            "name": "Regal Queen", "odds": 4.5, "form": "772588-",
            "jockeyName": "P Mongqawa", "trainerName": "F Bronkhorst",
            "draw": 1, "starRating": 68, "weight": "9st 4lbs",
        }])
    })
    clean = _snapshot({"e1": _race([{
        "name": "Regal Queen", "odds": "SP", "form": "",
        "jockeyName": "TBA", "trainerName": "TBA",
        "draw": 0, "starRating": 0, "weight": "0",
    }])})

    out = snapshot_writer.carry_forward_prices(clean, path)
    runner = out["events"]["e1"]["runners"][0]

    assert runner["odds"] == 4.5
    assert runner["price_carried"] is True
    assert runner["form"] == "772588-"
    assert runner["jockeyName"] == "P Mongqawa"
    assert runner["trainerName"] == "F Bronkhorst"
    assert runner["draw"] == 1
    assert runner["starRating"] == 68
    assert runner["weight"] == "9st 4lbs"


def test_carry_forward_never_overwrites_a_live_price(tmp_path):
    path = _write_previous(tmp_path, {
        "e1": _race([{"name": "Regal Queen", "odds": 9.9}])
    })
    clean = _snapshot({"e1": _race([{"name": "Regal Queen", "odds": 2.2}])})

    runner = snapshot_writer.carry_forward_prices(clean, path)["events"]["e1"]["runners"][0]

    assert runner["odds"] == 2.2
    assert "price_carried" not in runner


def test_carry_forward_skips_non_runners(tmp_path):
    path = _write_previous(tmp_path, {
        "e1": _race([{"name": "Scratched", "odds": 5.0}])
    })
    clean = _snapshot({"e1": _race([
        {"name": "Scratched", "odds": "SP", "non_runner": True}
    ])})

    runner = snapshot_writer.carry_forward_prices(clean, path)["events"]["e1"]["runners"][0]

    assert runner["odds"] == "SP"
    assert "price_carried" not in runner


def test_carry_forward_ignores_a_different_event(tmp_path):
    path = _write_previous(tmp_path, {
        "e1": _race([{"name": "Regal Queen", "odds": 4.5}])
    })
    clean = _snapshot({"e2": _race([{"name": "Regal Queen", "odds": "SP"}])})

    runner = snapshot_writer.carry_forward_prices(clean, path)["events"]["e2"]["runners"][0]

    assert runner["odds"] == "SP"


def test_carry_forward_matches_names_not_position(tmp_path):
    """A field that re-ordered must still get the right horse's price."""
    path = _write_previous(tmp_path, {
        "e1": _race([
            {"name": "Silver Chord", "odds": 3.4},
            {"name": "Winter Palace", "odds": 7.0},
        ])
    })
    clean = _snapshot({"e1": _race([
        {"name": "Winter Palace", "odds": "SP"},
        {"name": "Silver Chord", "odds": "SP"},
    ])})

    runners = snapshot_writer.carry_forward_prices(clean, path)["events"]["e1"]["runners"]

    assert runners[0]["odds"] == 7.0
    assert runners[1]["odds"] == 3.4


# ── 3. Durable Betway price table ───────────────────────────────────────────


@pytest.fixture
def price_cache(tmp_path, monkeypatch):
    path = tmp_path / "betway_prices_last_good.json"
    monkeypatch.setattr(betway_api, "BETWAY_PRICE_CACHE_PATH", str(path))
    monkeypatch.setattr(betway_api, "BETWAY_PRICE_CACHE_TTL_SECS", 3 * 3600)
    return path


def _priced_card(odds=4.5, **runner_extra):
    return {"events": {"e1": _race([{
        "name": "Regal Queen", "odds": odds, "form": "772588-",
        "jockeyName": "P Mongqawa", **runner_extra,
    }])}}


def test_price_cache_rehydrates_an_unpriced_race(price_cache):
    betway_api._save_price_cache(_priced_card())

    out = betway_api._apply_price_cache(
        {"events": {"e1": _race([{
            "name": "Regal Queen", "odds": "SP", "form": "",
            "jockeyName": "TBA",
        }])}, "daily_unpriced": 1}
    )
    runner = out["events"]["e1"]["runners"][0]

    assert runner["odds"] == 4.5
    assert runner["price_cached"] is True
    assert runner["form"] == "772588-"
    assert runner["jockeyName"] == "P Mongqawa"
    assert out["price_cache_used"] is True
    assert out["price_cache_restored"] == 1
    assert out["daily_unpriced"] == 0


def test_price_cache_never_overwrites_a_live_price(price_cache):
    betway_api._save_price_cache(_priced_card(odds=9.9))

    out = betway_api._apply_price_cache(_priced_card(odds=2.2))
    runner = out["events"]["e1"]["runners"][0]

    assert runner["odds"] == 2.2
    assert "price_cached" not in runner


def test_price_cache_hydrates_only_the_unpriced_races(price_cache):
    """A cycle that priced one meeting must not lose the others."""
    betway_api._save_price_cache({
        "events": {
            "e1": _race([{"name": "A", "odds": 4.5}], number=1),
            "e2": _race([{"name": "B", "odds": 6.0}], number=2),
        }
    })

    out = betway_api._apply_price_cache({"events": {
        "e1": _race([{"name": "A", "odds": 3.1}], number=1),
        "e2": _race([{"name": "B", "odds": "SP"}], number=2),
    }})

    assert out["events"]["e1"]["runners"][0]["odds"] == 3.1
    assert out["events"]["e2"]["runners"][0]["odds"] == 6.0


def test_price_cache_keeps_previous_races_across_cycles(price_cache):
    """A race that drops off today's card keeps its last price until the TTL."""
    betway_api._save_price_cache(_priced_card())
    betway_api._save_price_cache({
        "events": {"e2": _race([{"name": "Later Race", "odds": 3.3}], number=4)}
    })

    _, cached = betway_api._load_price_cache()
    assert {"e1", "e2"} == set(cached)


def test_price_cache_is_not_written_for_an_unpriced_card(price_cache):
    betway_api._apply_price_cache(
        {"events": {"e1": _race([{"name": "A", "odds": "SP"}])}}
    )
    assert not price_cache.exists()


def test_price_cache_expires_after_ttl(price_cache):
    price_cache.write_text(json.dumps({
        "ts": time.time() - (4 * 3600),
        "events": {"e1": {
            "cached_at": time.time() - (4 * 3600),
            "runners": [{"name": "Regal Queen", "odds": 4.5}],
        }},
    }))

    out = betway_api._apply_price_cache(
        {"events": {"e1": _race([{"name": "Regal Queen", "odds": "SP"}])}}
    )

    assert out["events"]["e1"]["runners"][0]["odds"] == "SP"
    assert "price_cache_used" not in out
