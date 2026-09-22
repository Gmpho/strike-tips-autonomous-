"""Regression tests for exotic settlement blockers (Sep-2026).

1. Dividend scrape hardcoded "yesterday" — a same-day winner could never find
   its tote dividend on the correct day's page (stuck "awaiting dividend").
2. Awaiting states were silent: no healing event, no leg-level diagnostics.
"""
import asyncio
import inspect
import json
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core_agent.skills import result_tracker as rt


# ── Dividend scrape uses the bet's own race day ─────────────────────────────


def _capture_urls():
    """Fake async client that records requested URLs and returns one page."""
    seen = []

    class FakeResp:
        status_code = 200

        def __init__(self):
            # >30 chars per line: _clean_html drops shorter fragments.
            self.text = (
                "<html><body><div>Vaal Race 2 Result — 22 September 2026</div>"
                "<div>1st Mary's Captain, 2nd Steel And Satin, 3rd Unvarnished Gold</div>"
                "<div>BIPOT PAYS R1 234,50 with a single winning combination</div>"
                "</body></html>"
            )

    class FakeClient:
        async def get(self, url, headers=None):
            seen.append(url)
            return FakeResp()

    return seen, FakeClient()


def test_dividend_scrape_uses_bet_date_first():
    seen, client = _capture_urls()
    tracker = rt.ResultTracker.__new__(rt.ResultTracker)

    with patch(
        "core_agent.core.http_client.get_async_client", return_value=client
    ):
        text = asyncio.run(
            tracker._scrape_sa_results_direct(
                "vaal", 2, bet_date="2026-09-22"
            )
        )

    assert text, "scrape returned nothing"
    assert seen, "no URLs requested"
    # The bet's own day is tried before today/yesterday fallbacks.
    assert "2026-09-22" in seen[0], f"bet date not preferred: {seen[0]}"
    assert seen[0].startswith("https://www.tab4racing.com/results/2026-09-22")


def test_dividend_scrape_falls_back_when_no_bet_date():
    seen, client = _capture_urls()
    tracker = rt.ResultTracker.__new__(rt.ResultTracker)

    with patch(
        "core_agent.core.http_client.get_async_client", return_value=client
    ):
        asyncio.run(tracker._scrape_sa_results_direct("vaal", 2))

    assert seen
    # No bet date → today first (still not the old hardcoded yesterday).
    assert date.today().isoformat() in seen[0]


def test_unknown_track_returns_none_without_fetching():
    seen, client = _capture_urls()
    tracker = rt.ResultTracker.__new__(rt.ResultTracker)
    with patch(
        "core_agent.core.http_client.get_async_client", return_value=client
    ):
        out = asyncio.run(tracker._scrape_sa_results_direct("ascot", 1))
    assert out is None
    assert not seen, "no fetch should happen for an unmapped track"


# ── Visibility: awaiting-dividend reported, leg diagnostics named ───────────


def test_awaiting_dividend_emits_healing_event():
    """A won ticket without a published dividend must be reported, not silent."""
    src = inspect.getsource(rt.ResultTracker._settle_exotic_ticket)
    assert "EXOTIC_AWAITING_DIVIDEND" in src
    assert "bet_date=getattr(bet" in src  # date threaded into the scrape


def test_unknown_legs_are_named_in_log(caplog):
    """Unresolved legs are logged by race number so PENDING explains itself."""
    src = inspect.getsource(rt.ResultTracker._settle_exotic_ticket)
    assert "awaiting results for leg(s)" in src


def test_healing_event_writes_file(tmp_path, monkeypatch):
    """The healing helper appends a well-formed event (never raises)."""
    import core_agent.config.paths as paths

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    rt._healing_event("EXOTIC_AWAITING_DIVIDEND", "BIPOT awaiting dividend", agent="ResultTracker", status="WARN")
    written = json.loads((tmp_path / "healing_events.json").read_text())
    assert written[-1]["action"] == "EXOTIC_AWAITING_DIVIDEND"
    assert written[-1]["status"] == "WARN"
