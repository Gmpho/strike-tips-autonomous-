"""Gate-order: /start ST-XXXXX redeems INSIDE the auth gate.

Regression pin for the original bug: the redeem lived after the gate, so
strangers hit the Restricted wall and passcode-first onboarding was
impossible (PIN-first workaround required).
"""
import pytest

from core_agent.core.telegram_gate import parse_start_code, redeem_and_authorize


@pytest.mark.parametrize("text,expected", [
    ("/start ST-12345", "ST-12345"),
    ("/start st-12345", "ST-12345"),
    ("  /start ST-99999  ", "ST-99999"),
    ("/start", None),
    ("/start hello", None),
    ("/start ST-123", None),
    ("/start ST-123456", None),
    ("/help", None),
    ("races at vaal", None),
])
def test_parse_start_code(text, expected):
    assert parse_start_code(text) == expected


class _FakeRepo:
    def __init__(self, ok=True):
        self._ok = ok
        self.calls = []

    def redeem_link_code(self, code, chat_id, username):
        self.calls.append((code, chat_id, username))
        return {"code": code} if self._ok else None


def _patch(monkeypatch, ok=True):
    import core_agent.db.client as cl
    import core_agent.core.access_control as ac
    import core_agent.skills.notifications.telegram_bot as tb

    repo = _FakeRepo(ok)
    monkeypatch.setattr(cl, "get_service_client", lambda: object())
    monkeypatch.setattr(
        "core_agent.db.repository.LedgerRepository", lambda client: repo)
    authed = []
    monkeypatch.setattr(ac, "authorize", lambda cid: authed.append(cid))
    cleared = []
    monkeypatch.setattr(tb, "clear_quarantine", lambda cid: cleared.append(cid) or True)
    return repo, authed, cleared


def test_redeem_success_authorizes_and_dequarantines(monkeypatch):
    repo, authed, cleared = _patch(monkeypatch, ok=True)
    assert redeem_and_authorize("ST-12345", 777, "@u") is True
    assert repo.calls == [("ST-12345", 777, "@u")]
    assert authed == [777]
    assert cleared == [777]


def test_redeem_failure_authorizes_nothing(monkeypatch):
    repo, authed, cleared = _patch(monkeypatch, ok=False)
    assert redeem_and_authorize("ST-00000", 777, "@u") is False
    assert authed == []
    assert cleared == []
