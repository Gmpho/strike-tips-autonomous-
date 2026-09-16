"""Tests for engine telemetry (core_agent.core.telemetry) — buffer, badges, fanout safety."""

import pytest

from core_agent.core import telemetry


@pytest.fixture(autouse=True)
def _isolated_file(tmp_path, monkeypatch):
    """Redirect the cross-container JSONL mirror to a temp file so tests
    never touch the real data/telemetry.jsonl."""
    monkeypatch.setattr(telemetry, "_telemetry_path", lambda: str(tmp_path / "telemetry.jsonl"))


def setup_function(_):
    telemetry.clear()


def test_emit_stores_event_newest_last():
    telemetry.emit("swarm", "first")
    telemetry.emit("news", "second")
    events = telemetry.get_events(10)
    assert events[0]["engine"] == "news"          # newest-first
    assert events[-1]["message"] == "first"
    assert len(events) == 2


def test_emit_defaults_badge_by_engine():
    ev = telemetry.emit("governor", "DSI check")
    assert ev["badge"] == "GOVERNOR CHECK"


def test_emit_custom_badge_and_truncation():
    ev = telemetry.emit("system", "x" * 500, badge="CUSTOM")
    assert ev["badge"] == "CUSTOM"
    assert len(ev["message"]) == 300


def test_ring_buffer_caps_at_max():
    for i in range(telemetry.MAX_EVENTS + 20):
        telemetry.emit("swarm", f"event-{i}")
    events = telemetry.get_events(1000)
    # Memory caps at MAX_EVENTS; the file mirror caps higher (250). The
    # merged view stays bounded by the file cap, newest survive.
    assert len(events) <= telemetry.TELEMETRY_FILE_MAX_LINES
    assert any("event-119" in e["message"] for e in events)


def test_get_latest_by_engine_returns_newest_per_engine():
    telemetry.emit("swarm", "swarm old")
    telemetry.emit("dream", "dream 1")
    telemetry.emit("swarm", "swarm new")
    latest = telemetry.get_latest_by_engine()
    assert set(latest.keys()) == {"swarm", "dream"}
    assert latest["swarm"]["message"] == "swarm new"


def test_emit_never_raises_without_event_loop():
    """Sync context (no running loop) must not blow up on fanout."""
    ev = telemetry.emit("news", "no-loop event")
    assert ev["engine"] == "news"


def test_clear_resets_memory_but_file_survives():
    """clear() wipes this process's buffer; the cross-container file mirror
    is intentionally untouched (that's how sibling containers see events)."""
    telemetry.emit("swarm", "gone soon")
    telemetry.clear()
    assert list(telemetry._buffer) == []
    assert any(e["message"] == "gone soon" for e in telemetry.get_events())


def test_correlation_bind_get_tag():
    from core_agent.core import correlation as corr

    assert corr.get() == "" or isinstance(corr.get(), str)
    cid = corr.bind(corr.new_id("settle"))
    assert cid.startswith("settle-") and len(cid) == len("settle-") + 8
    assert corr.get() == cid
    assert corr.tag() == f"[{cid}]"
    corr.bind("")
    assert corr.get() == "" and corr.tag() == ""
