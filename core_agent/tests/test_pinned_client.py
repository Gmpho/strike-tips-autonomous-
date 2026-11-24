"""One pinned browser per cycle, not one per request (2026-11-24).

``_http_get`` used to build a fresh client per call while ``get_impersonate()``
picked a random profile, so a single cycle fired ~83 GetEvent requests carrying
up to 83 different TLS fingerprints from one IP in ten seconds. These tests pin
that behaviour down: the profile is fixed, the client is reused across a burst,
and a new cycle starts from a clean session.
"""

from core_agent.core import http_client as hc
from core_agent.skills.parsers import betway_api as bw


def test_explicit_impersonate_overrides_random_rotation(monkeypatch):
    captured = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(hc, "AsyncSession", FakeSession)
    monkeypatch.setattr(hc, "Session", FakeSession)
    monkeypatch.setattr(hc.get_proxy_manager(), "get_impersonate", lambda: "firefox135")

    hc.get_async_client(impersonate="chrome131")

    assert captured["impersonate"] == "chrome131"


def test_rotation_still_applies_when_nothing_is_pinned(monkeypatch):
    """Other scrapers rely on rotation — pinning must be opt-in per source."""
    captured = {}

    class FakeSession:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(hc, "AsyncSession", FakeSession)
    monkeypatch.setattr(hc.get_proxy_manager(), "get_impersonate", lambda: "safari17_0")

    hc.get_async_client()

    assert captured["impersonate"] == "safari17_0"


def _patch_client(monkeypatch, built):
    class FakeClient:
        def __init__(self, **kwargs):
            built.append(kwargs)

    monkeypatch.setattr(bw, "get_async_client", lambda **kw: FakeClient(**kw))


def test_one_client_is_built_for_the_whole_burst(monkeypatch, tmp_path):
    monkeypatch.setattr(bw, "_EGRESS_STATE_PATH", str(tmp_path / "egress.json"))
    built = []
    _patch_client(monkeypatch, built)

    api = bw.BetwayAPI()
    first = api._client()
    second = api._client()

    assert first is second
    assert len(built) == 1
    assert built[0]["impersonate"] == bw.BetwayAPI.IMPERSONATE
    assert built[0]["no_proxy"] is True


def test_pinned_profile_is_chrome131(monkeypatch, tmp_path):
    monkeypatch.setattr(bw, "_EGRESS_STATE_PATH", str(tmp_path / "egress.json"))
    assert bw.BetwayAPI.IMPERSONATE == "chrome131"


def test_worker_proxy_advertises_the_same_browser(monkeypatch, tmp_path):
    """The proxy path used a Windows UA while the direct path used macOS."""
    monkeypatch.setattr(bw, "_EGRESS_STATE_PATH", str(tmp_path / "egress.json"))
    ua = bw.BetwayAPI.BROWSER_UA
    assert "Macintosh" in ua
    assert "Chrome/131" in ua
    assert "Windows" not in ua


def test_new_cycle_starts_a_fresh_client(monkeypatch, tmp_path):
    monkeypatch.setattr(bw, "_EGRESS_STATE_PATH", str(tmp_path / "egress.json"))
    built = []
    _patch_client(monkeypatch, built)

    api = bw.BetwayAPI()
    api._client()
    api.start_cycle()

    assert api._cycle_client is None
    api._client()
    assert len(built) == 2
