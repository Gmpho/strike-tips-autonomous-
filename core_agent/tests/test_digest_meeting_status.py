"""Digest meeting-status pins (Oct-2026).

Symptom: the Europe Intelligence digest showed "Found 7 value bet(s)" /
"Haydock — 7 selections" while the other four scanned meetings
(newcastle, redcar, uttoxeter, dundalk) vanished. Their analysis had
silently failed (Groq TPD + Gemini free-tier exhausted → empty AI
responses), and send_daily_tips gated every meeting on `vb_count > 0`,
so a failed meeting read exactly like "no value today".

Every scanned meeting must now be listed with an explicit status.
"""
import asyncio

from core_agent.skills.notifications.telegram_bot import TelegramNotifier


def _capture():
    """Notifier with broadcast stubbed, capturing the rendered digest."""
    notifier = TelegramNotifier.__new__(TelegramNotifier)
    sent = {}

    async def fake_broadcast(text, parse_mode="HTML"):
        sent["text"] = text
        return True

    notifier.broadcast = fake_broadcast
    return notifier, sent


def _race(number, **kw):
    base = {"track": "x", "race_number": number, "value_bets": []}
    base.update(kw)
    return base


def test_failed_meeting_no_longer_virtualised_as_no_value():
    """A meeting with an empty result list must be flagged, not dropped."""
    notifier, sent = _capture()
    scan = {
        "haydock": [_race(1, value_bets=[
            {"horse": "A", "odds_decimal": 3.0, "edge": 12.0}])],
        "dundalk": [],
    }

    asyncio.run(notifier.send_daily_tips(scan, title="Europe Intelligence Report"))
    text = sent["text"]

    assert "Haydock" in text and "1 selections" in text
    assert "Dundalk" in text
    assert "analysis unavailable" in text


def test_insight_but_no_bets_reads_as_no_value():
    """Zero bets WITH a parsed insight is genuinely 'no value', not a failure."""
    notifier, sent = _capture()
    scan = {"newcastle": [_race(1, ai_insight="No edge in this field.")]}

    asyncio.run(notifier.send_daily_tips(scan))
    text = sent["text"]

    assert "Newcastle" in text
    assert "no value found" in text
    assert "analysis unavailable" not in text
    assert "💡 No edge in this field." in text


def test_zero_value_meetings_still_render_insight_lines():
    """Insights must render even when a meeting has no value bets."""
    notifier, sent = _capture()
    scan = {"redcar": [_race(3, ai_insight="Raw")]}

    asyncio.run(notifier.send_daily_tips(scan))
    assert "R3: 💡 Raw" in sent["text"]


def test_non_dict_races_do_not_crash_the_digest():
    notifier, sent = _capture()
    scan = {"uttoxeter": [None, "junk", _race(1, ai_insight="ok")]}

    asyncio.run(notifier.send_daily_tips(scan))
    text = sent["text"]
    assert "Uttoxeter" in text
    assert "R1: 💡 ok" in text
