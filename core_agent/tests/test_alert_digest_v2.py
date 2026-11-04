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


def test_steady_rows_dropped_from_movers(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    asyncio.run(d.push("odds_drop", "x", meta=_meta(
        horse="Plodder", opened=4.5, latest=4.5)))
    asyncio.run(d.push("odds_drop", "x", meta=_meta(
        horse="Mover", opened=10.0, latest=5.0)))
    asyncio.run(d.flush_due(force=True))
    body = n.sent[0]
    assert "Plodder" not in body
    assert "Mover" in body
    assert "(1 mover(s)" in body


def test_junk_enrichment_values_filtered(tmp_path):
    n = _StubNotifier()
    d = AlertDigester(n, queue_path=str(tmp_path / "q.jsonl"))
    m = _meta()
    m["enrich"] = {"trainer": "S Ngcobo", "form": "0", "rating": "--",
                   "days": "N/A"}
    asyncio.run(d.push("odds_drop", "x", meta=m))
    asyncio.run(d.flush_due(force=True))
    body = n.sent[0]
    assert "S Ngcobo" in body
    assert "· 0 ·" not in body
    assert "watch only" in body


def test_expired_snapshot_race_never_alerts(tmp_path):
    import time as _time
    from core_agent.core.alert_engine import AlertCondition
    eng = AlertEngine(data_dir=str(tmp_path))
    eng.alerts_cache["g"] = AlertCondition(
        id="g", race_course="Any", horse_name=None,
        condition_type="threshold", condition_value="20.0",
        notification_channels=[], active=True, cooldown_minutes=0)
    race = {"course": "Kempton",
            "runners": [{"name": "Amorist", "odds": "13.0"}],
            "expires_at": _time.time() - 600}
    import asyncio as _a
    fired = []
    eng.notification_callback = lambda m: fired.append(m) or _a.sleep(0)
    _a.run(eng.evaluate_odds_update(race))
    assert fired == []


def test_unparseable_race_older_than_ttl_never_alerts(tmp_path):
    import time as _time
    from core_agent.core.alert_engine import AlertCondition
    eng = AlertEngine(data_dir=str(tmp_path))
    eng.alerts_cache["g"] = AlertCondition(
        id="g", race_course="Any", horse_name=None,
        condition_type="threshold", condition_value="20.0",
        notification_channels=[], active=True, cooldown_minutes=0)
    race = {"course": "Kempton", "first_seen": _time.time() - 7 * 3600,
            "runners": [{"name": "Amorist", "odds": "13.0"}]}
    import asyncio as _a
    fired = []
    eng.notification_callback = lambda m: fired.append(m) or _a.sleep(0)
    _a.run(eng.evaluate_odds_update(race))
    assert fired == []
