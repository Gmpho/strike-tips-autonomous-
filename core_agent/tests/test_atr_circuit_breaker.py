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
    monkeypatch.setattr(
        atr, "_breaker_probe_path", lambda: tmp_path / ".atr_probe_at"
    )
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
    """The breaker holds the per-race enrichment off completely."""
    flag.write_text(str(time.time() + 600))
    calls = []

    def boom(self, path, allow_stealth=True):
        calls.append(path)
        return b"should-not-run"

    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", boom)
    api = atr.AtTheRacesAPI()

    assert api._fetch("/racecard/Kenilworth/10-November-2026/1237",
                       allow_stealth=False) is None
    assert calls == []


def test_feed_fetch_probes_once_during_the_cooldown(flag, monkeypatch):
    """Half-open: one feed fetch per interval is still attempted, so ATR
    opening back up is noticed (the breaker could never self-heal before)."""
    flag.write_text(str(time.time() + 600))
    calls = []

    def boom(self, path, allow_stealth=True):
        calls.append(path)
        return None

    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", boom)
    api = atr.AtTheRacesAPI()

    api._fetch("/results/today")           # the probe
    assert calls == ["/results/today"]
    api._fetch("/results/today")           # inside the interval -> blocked
    assert calls == ["/results/today"]
    # Once the interval passes, another probe is allowed.
    monkeypatch.setattr(atr, "_BREAKER_PROBE_INTERVAL_SECS", 0)
    api._fetch("/results/today")
    assert len(calls) == 2


def test_probe_success_clears_the_breaker(flag, monkeypatch):
    """A successful probe ends the cooldown immediately."""
    flag.write_text(str(time.time() + 600))
    monkeypatch.setattr(
        atr.AtTheRacesAPI, "_fetch_tiered", lambda self, path, allow_stealth=True: b"ok"
    )
    api = atr.AtTheRacesAPI()
    assert api._fetch("/results/today") == b"ok"
    assert atr.atr_circuit_open() is False


def test_fetch_records_success_on_body(flag, monkeypatch):
    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", lambda self, p, allow_stealth=True: b"x" * 2000)
    api = atr.AtTheRacesAPI()

    assert api._fetch("/market-movers") == b"x" * 2000
    assert atr._breaker_failures == 0
    assert atr.atr_circuit_open() is False


def test_fetch_records_failure_on_empty(flag, monkeypatch):
    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", lambda self, p, allow_stealth=True: None)
    api = atr.AtTheRacesAPI()

    for _ in range(atr._BREAKER_FAILURE_THRESHOLD):
        assert api._fetch("/predictor") is None

    assert atr.atr_circuit_open() is True


def test_throttled_browser_tier_does_not_trip_breaker(flag, monkeypatch):
    """A miss while our own ≤1/hour throttle skipped the only working tier is
    self-inflicted, not the host blocking us — it must not accrue failures.

    Nov-2026: cheap 403s plus throttle skips tripped a 6h breaker every
    afternoon, freezing ATR snapshots for the whole evening card.
    """
    def throttled(self, path, allow_stealth=True):
        self._self_throttled = True
        return None

    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", throttled)
    api = atr.AtTheRacesAPI()

    for _ in range(atr._BREAKER_FAILURE_THRESHOLD * 2):
        assert api._fetch("/market-movers") is None

    assert atr._breaker_failures == 0
    assert atr.atr_circuit_open() is False


def test_genuine_failure_after_throttle_miss_still_counts(flag, monkeypatch):
    """The exemption must reset per fetch, not leak into the next attempt."""
    responses = ["throttled", "genuine"]

    def fake(self, path, allow_stealth=True):
        mode = responses.pop(0)
        self._self_throttled = mode == "throttled"
        assert self._self_throttled is (mode == "throttled")
        return None

    monkeypatch.setattr(atr.AtTheRacesAPI, "_fetch_tiered", fake)
    api = atr.AtTheRacesAPI()

    api._fetch("/market-movers")
    assert atr._breaker_failures == 0

    api._fetch("/market-movers")
    assert atr._breaker_failures == 1
