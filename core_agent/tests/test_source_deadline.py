"""Upstream source deadline guard (Oct-2026 odds freeze).

Production: ``run_single_cycle`` created the Betway / Racing-Odds / Betfair
tasks and then did ``state = await bw_task`` with no deadline. Betway's
``asyncio.gather`` over 400+ event details could stall on one socket that
curl_cffi never timed out, so the cycle blocked forever: no snapshot write, no
log line after the Betfair parse, and Modal killed the container at 900s on
every tick while the volume file stayed frozen for hours.

These tests pin ``_collect_sources``: the fetch phase must always finish, keep
whatever sources answered, and cancel the rest.
"""

import asyncio

import pytest

from core_agent.core.adaptive_odds_monitor import (
    SOURCE_PHASE_TIMEOUT_SECS,
    _collect_sources,
)


def _run(coro):
    return asyncio.run(coro)


def test_budget_fits_inside_modal_timeout():
    # The cron kills the container at 900s; the fetch phase must leave room
    # for the write, ATR refresh and alert flush that follow it.
    assert 0 < SOURCE_PHASE_TIMEOUT_SECS < 900


def test_all_sources_healthy():
    async def betway():
        return {"events": {"a": 1}, "count": 1}

    async def racing_odds():
        return {"events": {"b": 2}, "count": 1}

    async def betfair():
        return {"events": {"c": 3}, "count": 1}

    async def main():
        return await _collect_sources(
            {
                "betway": asyncio.create_task(betway()),
                "racing_odds": asyncio.create_task(racing_odds()),
                "betfair": asyncio.create_task(betfair()),
            },
            timeout=5,
        )

    result = _run(main())

    assert result["betway"] == {"events": {"a": 1}, "count": 1}
    assert result["racing_odds"] == {"events": {"b": 2}, "count": 1}
    assert result["betfair"] == {"events": {"c": 3}, "count": 1}


def test_hung_source_is_cancelled_and_others_survive():
    cancelled = []

    async def hung():
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    async def healthy():
        return {"events": {"b": 2}, "count": 1}

    async def main():
        return await _collect_sources(
            {
                "betway": asyncio.create_task(hung()),
                "racing_odds": asyncio.create_task(healthy()),
            },
            timeout=0.05,
        )

    result = _run(main())

    assert result["betway"] is None
    assert result["racing_odds"] == {"events": {"b": 2}, "count": 1}
    assert cancelled == [True], "hung task must be cancelled, not abandoned"


def test_failing_source_returns_none_without_raising():
    async def boom():
        raise RuntimeError("upstream 502")

    async def healthy():
        return {"events": {"b": 2}, "count": 1}

    async def main():
        return await _collect_sources(
            {
                "betway": asyncio.create_task(boom()),
                "betfair": asyncio.create_task(healthy()),
            },
            timeout=5,
        )

    result = _run(main())

    assert result["betway"] is None
    assert result["betfair"] == {"events": {"b": 2}, "count": 1}


def test_empty_snapshot_is_preserved_as_value_not_none():
    # A source that legitimately reports zero events must stay distinguishable
    # from one that failed, so callers can tell "no racing" from "no answer".
    async def empty():
        return {"events": {}, "count": 0}

    async def main():
        return await _collect_sources({"betway": asyncio.create_task(empty())}, timeout=5)

    assert _run(main())["betway"] == {"events": {}, "count": 0}
