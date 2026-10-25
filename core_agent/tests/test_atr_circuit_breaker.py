"""ATR fetch circuit breaker.

ATR moved behind Fastly bot protection in Oct-2026 and rejects every tier we
have (httpx 403, curl_cffi/Chromium challenge shells). The breaker keeps the
5-min odds cycle from stalling on a dead host and stops the staleness alarm
from firing forever against snapshots that cannot refresh.
"""

import time

import pytest

from core_agent.skills.parsers import attheraces_api as atr


@pytest.fixture
def flag(tmp_path, monkeypatch):
    path = tmp_path / ".atr_blocked_until"
    monkeypatch.setattr(atr, "_breaker_flag_path", lambda: path)
    monkeypatch.setattr(atr, "_breaker_failures", 0)
    return path


def test_trips_after_threshold(flag):
    for _ in range(atr._BREAKER_FAILURE_THRESHOLD - 1):
        atr._record_failure("/market-movers")
    assert atr.atr_circuit_open() is False

    atr._record_failure("/market-movers")
    assert atr.atr_circuit_open() is True
    assert float(flag.read_text()) > time.time()


def test_success_resets_breaker(flag):
    for _ in range(atr._BREAKER_FAILURE_THRESHOLD):
        atr._record_failure("/results/today")
    assert atr.atr_circuit_open() is True

    atr._record_success()
    assert atr.atr_circuit_open() is False
    assert not flag.exists()
    assert atr._breaker_failures == 0


def test_expired_cooldown_reopens_traffic(flag):
    flag.write_text(str(time.time() - 1))
    assert atr.atr_circuit_open() is False


def test_fetch_skips_tiers_while_open(flag, monkeypatch):
    flag.write_text(str(time.time() + 600))
    calls = []

    def boom(self, path):
        calls.append(path)
        return b"should-not-run"

    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", boom)
    api = atr.AtTheRacesAPI()

    assert api._fetch("/market-movers") is None
    assert calls == []


def test_fetch_records_success_on_body(flag, monkeypatch):
    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", lambda self, p: b"x" * 2000)
    api = atr.AtTheRacesAPI()

    assert api._fetch("/market-movers") == b"x" * 2000
    assert atr._breaker_failures == 0
    assert atr.atr_circuit_open() is False


def test_fetch_records_failure_on_empty(flag, monkeypatch):
    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", lambda self, p: None)
    api = atr.AtTheRacesAPI()

    for _ in range(atr._BREAKER_FAILURE_THRESHOLD):
        assert api._fetch("/predictor") is None

    assert atr.atr_circuit_open() is True
