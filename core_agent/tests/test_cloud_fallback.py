"""Cloud fallback behavior — mocked HTTP, zero spend.

Locks in: tool-vs-direct model routing, bounded 429 retries, and the fact
that 413 (oversized prompt) surfaces immediately so the *prompt diet* (not
blind retries) is the fix. Needs provider imports (conftest stubs binary
deps); skipped only if the chain itself is unimportable.
"""

import json
import pytest

groq_mod = pytest.importorskip(
    "core_agent.agent.providers.groq", reason="provider chain unimportable"
)
GroqProvider = groq_mod.GroqProvider


class FakeResp:
    def __init__(self, status_code, payload=None):
        self.status_code = status_code
        self._payload = payload or {"choices": [{"message": {"content": "ok"}}]}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, script):
        self.script = list(script)
        self.posts = []

    async def post(self, url, headers=None, json=None):
        self.posts.append(json)
        code = self.script.pop(0) if self.script else 200
        return FakeResp(code)


def _provider(monkeypatch, script):
    p = GroqProvider()
    p.api_key = "test-key"
    fake = FakeClient(script)
    monkeypatch.setattr(groq_mod, "get_async_client", lambda **kw: fake)
    return p, fake


def _msgs(text):
    return [{"role": "user", "content": text}]


async def _collect(gen):
    return "".join([c async for c in gen])


@pytest.mark.asyncio
async def test_tool_query_routes_to_flagship(monkeypatch):
    p, fake = _provider(monkeypatch, [200])
    out = await _collect(p.stream(_msgs("analyze this race for value"), None, None))
    assert out == "ok"
    assert fake.posts[0]["model"] == "openai/gpt-oss-120b"


@pytest.mark.asyncio
async def test_plain_chat_routes_to_fast(monkeypatch):
    p, fake = _provider(monkeypatch, [200])
    out = await _collect(p.stream(_msgs("tell me a joke"), None, None))
    assert out == "ok"
    assert fake.posts[0]["model"] == "openai/gpt-oss-20b"


@pytest.mark.asyncio
async def test_429_retries_once_then_succeeds(monkeypatch):
    p, fake = _provider(monkeypatch, [429, 200])
    out = await _collect(p.stream(_msgs("tell me a joke"), None, None))
    assert out == "ok"
    assert len(fake.posts) == 2  # bounded: 1 retry, not a loop


@pytest.mark.asyncio
async def test_429_exhausted_raises(monkeypatch):
    p, fake = _provider(monkeypatch, [429, 429])
    with pytest.raises(Exception):
        await _collect(p.stream(_msgs("tell me a joke"), None, None))
    assert len(fake.posts) == 2  # max_retries=1 → exactly 2 attempts


@pytest.mark.asyncio
async def test_413_surfaced_immediately(monkeypatch):
    """Oversized prompts must fail fast (fix the prompt, don't retry)."""
    p, fake = _provider(monkeypatch, [413])
    with pytest.raises(Exception):
        await _collect(p.stream(_msgs("tell me a joke"), None, None))
    assert len(fake.posts) == 1
