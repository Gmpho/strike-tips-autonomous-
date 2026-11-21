"""Mover digest must report real price moves, not just AlertEngine alerts.

The digester queue used to be fed exclusively from ``_on_alert``. A genuine
34.0 -> 51.0 drift recorded by ``diff_snapshot`` could therefore sit in the
canonical event store while the Telegram digest said "Quiet half hour", and
the only queued rows were stale re-alerts whose journey showed 0% movement.
"""

import pytest

from core_agent.core import adaptive_odds_monitor as mod


class _FakeDigester:
    def __init__(self):
        self.items = []

    async def push(self, category, html, meta=None):
        self.items.append((category, html, meta))

    async def push_critical(self, category, html):
        raise AssertionError("price moves must be batched, not critical")


def _monitor_with(digester):
    monitor = mod.AdaptiveOddsMonitor.__new__(mod.AdaptiveOddsMonitor)
    monitor._telegram_notifier = object()
    monitor._digester = digester
    return monitor


def _move(price=51.0, prev=34.0, name="Pulveriser", course="Sunshine Coast"):
    return {
        "id": "m1",
        "kind": "price_move",
        "race": {"course": course, "race_number": "10", "off": "16:20"},
        "runner": {"name": name},
        "book": "win",
        "prev": prev,
        "price": price,
        "move_pct": -50.0,
        "direction": "drifted",
        "source": "snapshot",
    }


@pytest.mark.asyncio
async def test_price_moves_are_queued_for_the_digest():
    digester = _FakeDigester()
    monitor = _monitor_with(digester)

    await monitor._queue_moves_for_digest([_move()])

    assert len(digester.items) == 1
    category, html, meta = digester.items[0]
    assert category == "odds_drop"
    assert "Pulveriser @ Sunshine Coast" in html
    assert meta["canonical_event"]["move_pct"] == -50.0
    assert meta["horse"] == "Pulveriser"


@pytest.mark.asyncio
async def test_digest_html_matches_alert_engine_for_dedupe():
    """Both producers must render the same key so a horse isn't reported twice."""
    digester = _FakeDigester()
    monitor = _monitor_with(digester)

    await monitor._queue_moves_for_digest([_move(price=17.0, prev=23.0)])

    _, html, _ = digester.items[0]
    assert html == "🐎 Pulveriser @ Sunshine Coast\n💰 Odds: 17.0"


@pytest.mark.asyncio
async def test_non_move_events_are_ignored():
    digester = _FakeDigester()
    monitor = _monitor_with(digester)
    other = {**_move(), "kind": "alert"}

    await monitor._queue_moves_for_digest([other])

    assert digester.items == []


@pytest.mark.asyncio
async def test_no_digester_is_a_no_op():
    """Telegram-disabled deployments must not break market event recording."""
    monitor = mod.AdaptiveOddsMonitor.__new__(mod.AdaptiveOddsMonitor)
    monitor._telegram_notifier = None
    monitor._digester = None

    await monitor._queue_moves_for_digest([_move()])  # does not raise


@pytest.mark.asyncio
async def test_feed_market_events_queues_moves(monkeypatch):
    """The monitor's write path actually hands diff results to the digest."""
    monitor = _monitor_with(_FakeDigester())
    called = []

    def fake_diff(state):
        called.append(state)
        return [_move()]

    monkeypatch.setattr("core_agent.core.market_events.diff_snapshot", fake_diff)

    await monitor._feed_market_events({"events": {"a": {}}})

    assert called and monitor._digester.items
