"""Telegram passcode-link endpoints: auth gating + code lifecycle.

Route handlers are called directly with a faked service client —
no live Supabase, no bot token.
"""
import re
import sys
import types

import pytest

from core_agent.routes import telegram_link as tl


class FakeAuth:
    def __init__(self, uid):
        self._uid = uid

    def get_user(self, token):
        if token != "good-jwt":
            raise Exception("invalid token")
        return types.SimpleNamespace(user=types.SimpleNamespace(id=self._uid))


class FakeTable:
    def __init__(self, store, name):
        self._s = store
        self._n = name
        self._f = []

    def select(self, *a, **k):
        self._op = "select"
        return self

    def insert(self, p):
        self._op = "insert"
        self._p = p
        return self

    def upsert(self, p, on_conflict=None):
        self._op = "upsert"
        self._p = p
        return self

    def update(self, p):
        self._op = "update"
        self._p = p
        return self

    def eq(self, c, v):
        self._f.append((c, v))
        return self

    def gt(self, c, v):
        self._f.append(("gt", c, v))
        return self

    def order(self, *a, **k):
        return self

    def limit(self, *a, **k):
        return self

    def _m(self, r):
        for f in self._f:
            if len(f) == 3:
                if f[0] == "gt":
                    continue  # expiry check: test rows are always fresh
                _, c, v = f
            else:
                c, v = f
            if r.get(c) != v:
                return False
        return True

    def execute(self):
        rows = self._s.setdefault(self._n, [])

        class R:
            def __init__(self, data):
                self.data = data

        if self._op == "select":
            return R([r for r in rows if self._m(r)])
        if self._op == "insert":
            rows.append(dict(self._p))
            return R([rows[-1]])
        if self._op == "upsert":
            for i, r in enumerate(rows):
                if all(r.get(k) == v for k, v in self._p.items()
                       if k in ("id", "user_id", "ref", "code_hash")):
                    rows[i] = {**r, **self._p}
                    return R([rows[i]])
            rows.append(dict(self._p))
            return R([rows[-1]])
        if self._op == "update":
            out = []
            for r in rows:
                if self._m(r):
                    r.update(self._p)
                    out.append(r)
            return R(out)
        raise AssertionError(self._op)


class FakeClient:
    def __init__(self):
        self.store = {}
        self.auth = FakeAuth("user-1")

    def table(self, name):
        return FakeTable(self.store, name)


@pytest.fixture()
def fake_service(monkeypatch):
    client = FakeClient()
    import core_agent.db.client as cl
    monkeypatch.setattr(cl, "get_service_client", lambda: client)
    return client


@pytest.mark.asyncio
async def test_link_code_requires_auth():
    with pytest.raises(Exception):
        await tl.link_code(authorization=None)


@pytest.mark.asyncio
async def test_link_code_mints_st_code(fake_service):
    out = await tl.link_code(authorization="Bearer good-jwt")
    assert re.match(r"^ST-\d{5}$", out["code"])
    assert out["expires_in_minutes"] == 15


def test_ensure_profile_idempotent():
    from core_agent.db.repository import LedgerRepository
    repo = LedgerRepository(FakeClient())
    repo.ensure_profile("user-1")
    repo.ensure_profile("user-1")  # second call: no duplicate, no error


@pytest.mark.asyncio
async def test_status_unlinked_then_linked(fake_service):
    from core_agent.db.repository import LedgerRepository
    s1 = await tl.link_status(authorization="Bearer good-jwt")
    assert s1 == {"linked": False, "username": None}
    repo = LedgerRepository(fake_service)
    code = repo.create_link_code("user-1")
    repo.redeem_link_code(code, 777, "@punter")
    s2 = await tl.link_status(authorization="Bearer good-jwt")
    assert s2 == {"linked": True, "username": "@punter"}


@pytest.mark.asyncio
async def test_unlink_revokes(fake_service):
    from core_agent.db.repository import LedgerRepository
    repo = LedgerRepository(fake_service)
    code = repo.create_link_code("user-1")
    repo.redeem_link_code(code, 777, "@punter")
    out = await tl.unlink(authorization="Bearer good-jwt")
    assert out["ok"] is True and out["revoked"] == 1
    s = await tl.link_status(authorization="Bearer good-jwt")
    assert s["linked"] is False
