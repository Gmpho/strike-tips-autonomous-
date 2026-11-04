import sys
import types

# Stub curl_cffi (Docker-only binary dep) so parser modules import locally.
# Only stub when the real package is genuinely absent -- if it's installed
# (e.g. inside Docker), the real module must win or chromadb/httpx break.
try:
    import curl_cffi  # noqa: F401
except ImportError:
    if "curl_cffi" not in sys.modules:
        _curl = types.ModuleType("curl_cffi")
        _curl_opt = types.ModuleType("curl_cffi.curl")
        _curl_opt.CurlOpt = types.SimpleNamespace(RESOLVE="resolve")
        _requests = types.ModuleType("curl_cffi.requests")
        _requests.AsyncSession = lambda **k: None
        _requests.Session = lambda **k: None
        sys.modules["curl_cffi"] = _curl
        sys.modules["curl_cffi.curl"] = _curl_opt
        sys.modules["curl_cffi.requests"] = _requests
        _curl.curl = _curl_opt
        _curl.requests = _requests

# Stub httpx (Docker-only dep) so monitor imports locally.
# Only stub when httpx is genuinely not installed -- never shadow a real
# install, because chromadb requires the full httpx API (Limits, etc.).
try:
    import httpx  # noqa: F401
except ImportError:
    if "httpx" not in sys.modules:
        class _StubResp:
            status_code = 200
            def raise_for_status(self): return None
            def json(self): return {}
            @property
            def text(self): return ""
        class _StubAsyncClient:
            def __init__(self, *a, **k): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *a): return None
            async def post(self, *a, **k): return _StubResp()
            async def get(self, *a, **k): return _StubResp()
        class _StubClient:
            def __init__(self, *a, **k): pass
            def post(self, *a, **k): return _StubResp()
            def get(self, *a, **k): return _StubResp()
        _httpx = types.ModuleType("httpx")
        _httpx.AsyncClient = _StubAsyncClient
        _httpx.Client = _StubClient
        _httpx.Response = _StubResp
        _httpx.TimeoutException = Exception
        _httpx.ConnectError = Exception
        sys.modules["httpx"] = _httpx


import os  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True, scope="session")
def _isolate_search_cache(tmp_path_factory):
    """Keep the durable search cache out of the repo's data dir.

    ``search_service`` memoises query answers on disk (6h, 20 min for empty
    results) so repeated monitor queries cost nothing across cron containers.
    That is correct in production and poisonous in tests: mocked answers used
    to land in ``data/search_cache.json``, so the *next* suite run served
    "https://a.com/1" from disk instead of calling Tavily, and the provider
    tests failed on nothing but run order.
    """
    scratch = tmp_path_factory.mktemp("search-cache") / "search_cache.json"
    os.environ["SEARCH_CACHE_PATH"] = str(scratch)
    import core_agent.skills.search_service as _ss

    _ss._cache.clear()
    yield
    os.environ.pop("SEARCH_CACHE_PATH", None)
    _ss._cache.clear()
