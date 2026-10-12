"""Alert Digest v2: journey rows, collapse, framing. Pure-render tests —
no network, no Telegram."""

import asyncio
import json

from core_agent.core.alert_digester import AlertDigester
from core_agent.core.alert_engine import AlertEngine


class _StubNotifier:
    def __init__(self):
        self.sent: list[str] = []

    async def broadcast(self, text: str, parse_mode: str = "HTML") -> bool:
        self.sent.append(text)
        return True


def _digester(tmp_path):
    return AlertDigester(_StubNotifier(),
                         queue_path=str(tmp_path / "q.jsonl"))


def _meta(horse="Sonyourastar", course="Worcester", race="7",
          opened=10.0, latest=2.5):
    return {
        "course": course, "horse": horse, "odds": latest, "race": race,
        "off": "14:55", "mins_to_off": 5,
        "journey": {"open": opened, "open_at": "2026-10-12T10:00",
                    "latest": latest, "latest_at": "2026-10-12T14:55"},
        "enrich": {"trainer": "S Ngcobo", "form": "312"},
        "timestamp": "2026-10-12T14:55",
    }


def test_repeats_collapse_to_one_trail_line(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    for odds in (11.0, 9.0, 9.5):
        asyncio.run(d.push("odds_drop", "x", meta=_meta(
            horse="Spong Hill", course="Yarmouth", race="",
            opened=11.0, latest=odds)))
    asyncio.run(d.flush_due(force=True))
    assert len(n.sent) == 1
    body = n.sent[0]
    assert body.count("Spong Hill") == 1
    assert "11.0" in body and "9.5" in body


def test_row_has_race_context_and_action(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    asyncio.run(d.push("odds_drop", "x", meta=_meta()))
    asyncio.run(d.flush_due(force=True))
    body = n.sent[0]
    assert "Worcester R7" in body
    assert "STEAMER" in body
    assert "watch only" in body  # no edge rated


def test_edge_marker_when_rated(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    m = _meta()
    m["enrich"] = dict(m["enrich"], edge=6.2)
    asyncio.run(d.push("odds_drop", "x", meta=m))
    asyncio.run(d.flush_due(force=True))
    assert "★ Edge +6.2%" in n.sent[0]


def test_legacy_html_without_meta_still_renders(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    asyncio.run(d.push("odds_drop", "🐎 Plain @ Old"))
    asyncio.run(d.flush_due(force=True))
    assert "🐎 Plain @ Old" in n.sent[0]


def test_header_disclaims_tips(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    asyncio.run(d.push("odds_drop", "x", meta=_meta()))
    asyncio.run(d.flush_due(force=True))
    assert "not tips" in n.sent[0]


def test_journey_open_and_latest(tmp_path):
    eng = AlertEngine(data_dir=str(tmp_path))
    j1 = eng._record_sighting("Worcester", "7", "Sonyourastar", 10.0)
    assert j1["open"] == 10.0 and j1["latest"] == 10.0
    j2 = eng._record_sighting("Worcester", "7", "Sonyourastar", 2.5)
    assert j2["open"] == 10.0 and j2["latest"] == 2.5


def test_journey_prunes_other_days(tmp_path):
    eng = AlertEngine(data_dir=str(tmp_path))
    eng._journey = {"2000-01-01|X|1|Y": {"open": 1}}
    eng._load_journey()
    assert eng._journey == {}


def test_move_pct_direction():
    assert (AlertDigester._move_pct(
        {"journey": {"open": 10.0, "latest": 2.5}}) or 0) > 0
    assert (AlertDigester._move_pct(
        {"journey": {"open": 2.0, "latest": 8.0}}) or 0) < 0
    assert AlertDigester._move_pct({}) is None
