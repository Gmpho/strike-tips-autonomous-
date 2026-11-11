"""The results tab's display data: prices and form.

Nov-2026: the results tab printed "· —" in the Odds column for every
confirmed (Raceform) card and in the Form column for every runner of every
card. Prices live in ``odds_decimal`` on the card while the HUD reads
``runner.odds``; form lives in the Betfair enrichment the monitor keeps,
which nothing had joined to the result cards.
"""
import asyncio

from core_agent.routes.monitoring import _attach_form
from core_agent.core.strike_tips import _tab_meeting_date


def test_attach_form_fills_the_betfair_form(monkeypatch):
    import core_agent.core.strike_tips as st

    monkeypatch.setattr(
        st, "_bf_form_index",
        lambda data_dir, max_age_secs=6 * 3600: {
            ("fairview", 2): [{"name": "Joker Man", "form": "3-1-0"}],
        },
    )
    races = [{
        "course": "Fairview (RSA)",
        "title": "2\n10:50 - Stakes",
        "runners": [{"name": "Joker Man (2)"}, {"name": "Coastal Path (5)"}],
    }]
    out = _attach_form(races)
    # The saddle number is stripped before matching.
    assert out[0]["runners"][0]["form"] == "3-1-0"
    # A horse the Betfair card does not know keeps no form (never a guess).
    assert not out[0]["runners"][1].get("form")


def test_attach_form_leaves_cards_alone_without_an_index(monkeypatch):
    import core_agent.core.strike_tips as st

    monkeypatch.setattr(st, "_bf_form_index", lambda data_dir, max_age_secs=6 * 3600: {})
    races = [{"course": "Fairview (RSA)", "title": "2\n10:50", "runners": [{"name": "A"}]}]
    assert _attach_form(races) == races


def test_tab_meeting_date_reads_the_live_feed(monkeypatch):
    """An undated card must learn its meeting's day from TAB, or stay
    unknown — never be stamped with today's date (Nov-2026: 22 exotic
    tickets dated Wednesday for Friday/Saturday meetings)."""
    import core_agent.core.strike_tips as st

    class _Program:
        program_name = "TAB Fairview"
        program_date = "2026-11-11"

    async def fake_programs(ttl_secs=900):
        return [_Program()]

    monkeypatch.setattr(st, "_tab_programs", fake_programs)
    assert asyncio.run(st._tab_meeting_date("Fairview")) == "2026-11-11"
    # A track the feed does not list today is not running today: unknown.
    assert asyncio.run(st._tab_meeting_date("Turffontein")) == ""
    assert asyncio.run(st._tab_meeting_date("")) == ""
