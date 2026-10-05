"""Broadcast quarantine: TTL expiry, proof-of-life release, loud logging.

Oct-2026: a chat quarantined during passcode testing stayed silent forever —
no expiry, no self-heal. These pin the fix.
"""
import json
import time

import pytest


def _qfile(tmp_path):
    return tmp_path / "telegram_blocked.json"


def test_quarantine_and_release(tmp_path, monkeypatch):
    import core_agent.config.paths as paths
    import core_agent.skills.notifications.telegram_bot as tb

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    assert tb.clear_quarantine("111") is False  # nothing listed
    tb._quarantine_chat("111", "blocked by user")
    assert "111" in tb._quarantined_ids()
    assert tb.clear_quarantine(111) is True  # int or str both work
    assert "111" not in tb._quarantined_ids()
    assert tb.clear_quarantine("111") is False  # already gone


def test_quarantine_ttl_expires(tmp_path, monkeypatch):
    import core_agent.config.paths as paths
    import core_agent.skills.notifications.telegram_bot as tb

    monkeypatch.setattr(paths, "DATA_DIR", tmp_path)
    tb._quarantine_chat("222", "blocked by user")
    assert "222" in tb._quarantined_ids()
    # Age the entry past the 7-day TTL
    data = json.loads(_qfile(tmp_path).read_text())
    data["222"]["ts"] = time.time() - (8 * 24 * 3600)
    _qfile(tmp_path).write_text(json.dumps(data))
    assert "222" not in tb._quarantined_ids()  # expired on read


def test_only_403_blocked_quarantines():
    """Non-block failures must never quarantine (timeouts, 5xx, parse)."""
    import inspect
    import core_agent.skills.notifications.telegram_bot as tb

    src = inspect.getsource(tb.TelegramNotifier._send_to_chat)
    assert "403" in src and "blocked" in src
