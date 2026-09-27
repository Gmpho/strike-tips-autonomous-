"""Durable alert digester — the queue must survive container churn.

Sep-2026 regression: the digester kept its queue in memory with a 30-min
flush loop; Modal cron containers exit after one cycle and serve
containers scale to zero in ~60s, so every queued alert was discarded
("alerts are no longer coming"). These tests pin the file-backed queue
and age-based flush semantics.
"""

import asyncio
import json
import time

from core_agent.core.alert_digester import AlertDigester


class _StubNotifier:
    """Collects broadcasts; can be told to fail."""

    def __init__(self, ok: bool = True):
        self.ok = ok
        self.sent: list[str] = []

    async def broadcast(self, text: str, parse_mode: str = "HTML") -> bool:
        self.sent.append(text)
        return self.ok


def _digester(tmp_path, notifier) -> AlertDigester:
    # No start(): keeps the test free of background tasks; flush_due works
    # regardless of the loop, exactly like the monitor-cron call path.
    return AlertDigester(notifier, queue_path=str(tmp_path / "q.jsonl"))


def test_push_persists_to_queue_file(tmp_path):
    notifier = _StubNotifier()
    d = _digester(tmp_path, notifier)
    asyncio.run(d.push("odds_drop", "🐎 Horse A @ Track"))

    lines = (tmp_path / "q.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["category"] == "odds_drop"
    assert rec["html"] == "🐎 Horse A @ Track"
    assert rec["ts"] > 0


def test_flush_due_keeps_fresh_entries(tmp_path):
    notifier = _StubNotifier()
    d = _digester(tmp_path, notifier)
    asyncio.run(d.push("odds_drop", "fresh"))

    sent = asyncio.run(d.flush_due())
    assert sent == 0
    assert notifier.sent == []
    assert len((tmp_path / "q.jsonl").read_text().strip().splitlines()) == 1


def test_flush_due_ships_old_entries_and_clears(tmp_path):
    notifier = _StubNotifier()
    d = _digester(tmp_path, notifier)
    stale = {"ts": time.time() - 3600, "category": "odds_drop", "html": "old"}
    fresh = {"ts": time.time(), "category": "value_bet", "html": "fresh"}
    (tmp_path / "q.jsonl").write_text(json.dumps(stale) + "\n" + json.dumps(fresh) + "\n")

    sent = asyncio.run(d.flush_due())
    assert sent == 1
    assert len(notifier.sent) == 1
    assert "old" in notifier.sent[0]

    remaining = (tmp_path / "q.jsonl").read_text().strip().splitlines()
    assert len(remaining) == 1
    assert json.loads(remaining[0])["html"] == "fresh"


def test_failed_send_keeps_entries_for_retry(tmp_path):
    notifier = _StubNotifier(ok=False)
    d = _digester(tmp_path, notifier)
    stale = {"ts": time.time() - 3600, "category": "odds_drop", "html": "old"}
    (tmp_path / "q.jsonl").write_text(json.dumps(stale) + "\n")

    sent = asyncio.run(d.flush_due())
    assert sent == 0
    assert len((tmp_path / "q.jsonl").read_text().strip().splitlines()) == 1

    # Next flush with a healthy notifier ships it — never lost.
    notifier.ok = True
    sent = asyncio.run(d.flush_due())
    assert sent == 1
    assert (tmp_path / "q.jsonl").read_text().strip() == ""


def test_force_flush_sends_everything(tmp_path):
    notifier = _StubNotifier()
    d = _digester(tmp_path, notifier)
    asyncio.run(d.push("odds_drop", "fresh"))

    asyncio.run(d.flush())
    assert len(notifier.sent) == 1
    assert (tmp_path / "q.jsonl").read_text().strip() == ""


def test_corrupt_queue_lines_are_skipped(tmp_path):
    notifier = _StubNotifier()
    d = _digester(tmp_path, notifier)
    stale = {"ts": time.time() - 3600, "category": "value_bet", "html": "good"}
    (tmp_path / "q.jsonl").write_text("not json\n" + json.dumps(stale) + "\n\n")

    sent = asyncio.run(d.flush_due())
    assert sent == 1
    assert "good" in notifier.sent[0]
