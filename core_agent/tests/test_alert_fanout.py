"""Alert fan-out regression pins (Sep-2026).

Symptom: every digest carried ONE horse ("1 alert(s) in the last 30 min")
and the same race kept reappearing instead of 5-10 alerts across markets.

Root cause: AdaptiveOddsMonitor._on_alert held a SINGLE global timestamp —
the first trigger in a sweep set it, and every other runner in all ~40 races
was suppressed for the cooldown. Now the gate is per race+horse.
"""

import asyncio
import inspect
from datetime import datetime

import pytest

from core_agent.core.adaptive_odds_monitor import AdaptiveOddsMonitor


def _monitor_with_fakes():
    """Monitor instance with stubbed notifier/digester (no init side effects)."""
    mon = AdaptiveOddsMonitor.__new__(AdaptiveOddsMonitor)
    mon._telegram_notifier = object()

    pushed = []

    class FakeDigester:
        async def push(self, category, html):
            pushed.append((category, html))

        async def push_critical(self, category, html):
            pushed.append((category, html))

    mon._digester = FakeDigester()
    mon._last_alert_by_key = {}
    mon._alert_cooldown = 120.0
    return mon, pushed


def test_different_horses_alert_in_one_sweep():
    """Several markets/horses in the same cycle must all reach the digester."""
    mon, pushed = _monitor_with_fakes()

    async def sweep():
        for course, horse in [
            ("Listowel", "Nemorino"),
            ("Listowel", "Soaring Sun"),
            ("Ffos Las", "Georg Zhukov"),
            ("Fairyhouse", "Prince Of Peppard"),
        ]:
            await mon._on_alert({
                "type": "odds_drop", "horse": horse, "course": course, "odds": 5.5,
            })

    asyncio.run(sweep())
    assert len(pushed) == 4, f"only {len(pushed)} alerts survived the sweep"


def test_same_horse_is_rate_limited():
    mon, pushed = _monitor_with_fakes()

    async def twice():
        msg = {"type": "odds_drop", "horse": "Nemorino", "course": "Listowel", "odds": 5.5}
        await mon._on_alert(msg)
        await mon._on_alert(msg)

    asyncio.run(twice())
    assert len(pushed) == 1


def test_global_gate_is_gone():
    """No single global timestamp may gate all alerts."""
    src = inspect.getsource(AdaptiveOddsMonitor._on_alert)
    assert "_last_alert_by_key" in src
    assert "_last_alert_ts" not in src


def test_gate_dict_is_bounded():
    mon, _ = _monitor_with_fakes()
    base = datetime.now().timestamp()
    mon._last_alert_by_key = {f"c{i}::h{i}": base + i for i in range(2000)}
    asyncio.run(mon._on_alert({
        "type": "odds_drop", "horse": "New", "course": "Vaal", "odds": 4.0,
    }))
    assert len(mon._last_alert_by_key) <= 2001


def test_digester_reports_suppressed_counts():
    """A thin digest must explain cooldown suppressions instead of hiding them."""
    import core_agent.core.alert_digester as ad
    from core_agent.core.alert_digester import AlertDigester

    sent = []

    class FakeNotifier:
        async def broadcast(self, text, parse_mode="HTML"):
            sent.append(text)

    dig = AlertDigester(FakeNotifier(), interval=300)
    dig.note_suppressed({"race_cooldown_prevents": 7, "cooldown_prevents": 3})

    async def run():
        await dig.push("odds_drop", "🐎 Test @ Vaal\n💰 Odds: 4.5")
        await dig.flush()

    asyncio.run(run())
    assert sent, "digest did not flush"
    body = sent[-1]
    assert "Suppressed" in body
    assert "7 by per-race cooldown" in body
    assert "3 by per-horse cooldown" in body
