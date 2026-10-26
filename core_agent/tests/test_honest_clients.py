"""Honest-client policy: identity, pacing, deny list, no TLS impersonation."""

import asyncio
import logging

import pytest

from core_agent.config import compliance
from core_agent.core import http_client


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in (compliance.UA_ENV, compliance.IMPERSONATE_ENV, compliance.DENY_ENV):
        monkeypatch.delenv(var, raising=False)
    compliance.reset_throttle()
    yield
    compliance.reset_throttle()


def test_default_user_agent_identifies_the_project():
    ua = compliance.user_agent()
    assert ua == compliance.DEFAULT_USER_AGENT
    assert ua.startswith("strike-tips/")
    assert "Mozilla" not in ua


def test_user_agent_env_override(monkeypatch):
    monkeypatch.setenv(compliance.UA_ENV, "custom-agent/2.0")
    assert compliance.user_agent() == "custom-agent/2.0"


def test_impersonation_is_off_by_default():
    assert compliance.impersonate_profile() is None


def test_impersonation_opt_in_is_loud(monkeypatch, caplog):
    monkeypatch.setenv(compliance.IMPERSONATE_ENV, "chrome131")
    with caplog.at_level(logging.WARNING, logger="compliance"):
        assert compliance.impersonate_profile() == "chrome131"
    assert any("evasion" in r.message.lower() for r in caplog.records)


def test_known_hosts_have_declared_pacing():
    assert compliance.policy_for("https://www.betway.co.za/sportsapi/v1").min_interval_secs == 5.0
    assert compliance.policy_for("https://www.tab.co.za/racecards").min_interval_secs == 3.0
    assert compliance.policy_for("https://totex-col.4racing.com/x").allowed


def test_unlisted_host_gets_default_pacing():
    policy = compliance.policy_for("https://example.org/whatever")
    assert policy.allowed
    assert policy.min_interval_secs == compliance.DEFAULT_MIN_INTERVAL_SECS


def test_deny_list_wins_and_covers_subdomains(monkeypatch):
    monkeypatch.setenv(compliance.DENY_ENV, "betway.co.za")
    assert compliance.policy_for("https://www.betway.co.za/x").allowed is False
    with pytest.raises(compliance.PolicyViolation):
        compliance.check_allowed("https://www.betway.co.za/sportsapi/v1")


def test_throttle_reserves_sequential_slots():
    first = compliance.reserve_slot("https://www.tab.co.za/a")
    second = compliance.reserve_slot("https://www.tab.co.za/b")
    assert first == 0.0
    assert 0.0 < second <= 3.05


def test_throttle_is_per_host():
    compliance.reserve_slot("https://www.tab.co.za/a")
    other = compliance.reserve_slot("https://www.raceform.co.za/b")
    assert other == 0.0


def test_sessions_are_policy_clients_without_impersonation():
    sync = http_client.get_sync_client(timeout=1)
    async_ = http_client.get_async_client(timeout=1)
    try:
        assert isinstance(sync, http_client.PolicySession)
        assert isinstance(async_, http_client.AsyncPolicySession)
        assert sync.impersonate is None
        assert async_.impersonate is None
    finally:
        sync.close()
        asyncio.run(async_.close())


def test_policy_headers_keep_caller_user_agent():
    honest = http_client._policy_headers("https://www.tab.co.za/x", None)
    assert honest["User-Agent"] == compliance.DEFAULT_USER_AGENT
    custom = http_client._policy_headers(
        "https://www.tab.co.za/x", {"user-agent": "caller/1.0"}
    )
    assert custom == {"user-agent": "caller/1.0"}
