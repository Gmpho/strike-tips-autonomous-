"""Tests for engine telemetry (core_agent.core.telemetry) — buffer, badges, fanout safety."""

from core_agent.core import telemetry


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
    assert len(events) <= telemetry.MAX_EVENTS
    # Oldest dropped: newest message survives
    assert any("event-119" in e["message"] for e in events)
    assert not any("event-0" in e["message"] for e in events)


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


def test_clear_resets_buffer():
    telemetry.emit("swarm", "gone soon")
    telemetry.clear()
    assert telemetry.get_events() == []
