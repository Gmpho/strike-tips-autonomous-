// Runtime decision-table verification for functions/api/[[catchall]].ts.
// Real onRequest, real crypto, real env semantics — ONLY globalThis.fetch is
// stubbed, so nothing leaves the machine. Zero new dependencies.
// Run: node --test tests/catchall.test.ts
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import { mint } from "../functions/lib/session.ts";

const MASTER = "master-key-for-tests";
const SESSION = "test-secret-for-unit-tests-only";

interface FnCtx {
  request: Request;
  env: Record<string, string | undefined>;
  params: Record<string, string | string[]>;
  waitUntil(p: Promise<unknown>): void;
  passThroughOnException(): void;
  next(input?: RequestInfo | URL, init?: RequestInit): Promise<Response>;
  data: Record<string, unknown>;
}

type OnRequest = (ctx: FnCtx) => Promise<Response>;
let mod: { onRequest: OnRequest };

function makeCtx(request: Request, env: Record<string, string | undefined>): FnCtx {
  return {
    request,
    env,
    params: {},
    waitUntil() {},
    passThroughOnException() {},
    next: async () => new Response("next", { status: 200 }),
    data: {},
  };
}

function makeRequest(method: string, path: string, opts: { token?: string; key?: string } = {}): Request {
  const headers = new Headers({ "Content-Type": "application/json", "cf-connecting-ip": "203.0.113.9" });
  if (opts.token) headers.set("Cookie", `st_session=${encodeURIComponent(opts.token)}`);
  if (opts.key) headers.set("x-api-key", opts.key);
  return new Request(`https://hud.example${path}`, { method, headers, body: method === "GET" ? undefined : "{}" });
}

describe("catchall auth decision table", () => {
  let calls: Array<{ url: string; key: string }>;
  let realFetch: typeof fetch;

  beforeEach(async () => {
    if (!mod) {
      mod = (await import(new URL("../functions/api/%5B%5Bcatchall%5D%5D.ts", import.meta.url).href)) as unknown as { onRequest: OnRequest };
    }
    realFetch = globalThis.fetch;
    calls = [];
    (globalThis as unknown as { fetch: typeof fetch }).fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const h = new Headers(init?.headers);
      calls.push({ url: String(input), key: h.get("X-API-KEY") || "" });
      return new Response('{"ok":true}', { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
  });

  it("anonymous write -> 401, nothing forwarded", async () => {
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/config"), { BACKEND_API_KEY: MASTER }));
    assert.equal(res.status, 401);
    assert.equal(calls.length, 0);
  });

  it("valid session token + no master key -> /api/config forwards with master key injected", async () => {
    const token = await mint({ secret: SESSION, challengePassed: true });
    assert.ok(token);
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/config", { token: token! }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
    assert.equal(res.status, 200);
    assert.equal(calls.length, 1);
    assert.equal(calls[0].key, MASTER);
  });

  it("same path without a token -> 401", async () => {
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/config"), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
    assert.equal(res.status, 401);
    assert.equal(calls.length, 0);
  });

  it("kill with session token only -> 401, Modal never contacted", async () => {
    const token = await mint({ secret: SESSION, challengePassed: true });
    assert.ok(token);
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/agent/kill", { token: token! }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
    assert.equal(res.status, 401);
    assert.equal(calls.length, 0);
  });

  it("reset with session token only -> 401, Modal never contacted", async () => {
    const token = await mint({ secret: SESSION, challengePassed: true });
    assert.ok(token);
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/agent/reset", { token: token! }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
    assert.equal(res.status, 401);
    assert.equal(calls.length, 0);
  });

  it("betting write with session token only -> 401 (session never covers betting)", async () => {
    const token = await mint({ secret: SESSION, challengePassed: true });
    assert.ok(token);
    const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/betting/status", { token: token! }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
    assert.equal(res.status, 401);
    assert.equal(calls.length, 0);
  });

  it("master key still works everywhere it did before", async () => {
    for (const path of ["/api/config", "/api/healing/pulse", "/api/agent/kill"]) {
      const res = await mod.onRequest(makeCtx(makeRequest("POST", path, { key: MASTER }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
      assert.equal(res.status, 200, path);
    }
    assert.equal(calls.length, 3);
  });

  it("tampered/expired session token -> 401", async () => {
    const token = await mint({ secret: SESSION, challengePassed: true });
    assert.ok(token);
    const bad = token!.slice(0, -2) + "AA";
    for (const t of [bad, "garbage", ""]) {
      const res = await mod.onRequest(makeCtx(makeRequest("POST", "/api/config", { token: t }), { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION }));
      assert.equal(res.status, 401);
    }
    assert.equal(calls.length, 0);
  });
});

describe("task 4.1: full accept/deny matrix", () => {
  let realFetch: typeof fetch;
  let calls: Array<{ url: string; key: string }>;
  let sessionToken: string;

  beforeEach(async () => {
    if (!mod) {
      mod = (await import(new URL("../functions/api/%5B%5Bcatchall%5D%5D.ts", import.meta.url).href)) as unknown as { onRequest: OnRequest };
    }
    realFetch = globalThis.fetch;
    calls = [];
    (globalThis as unknown as { fetch: typeof fetch }).fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
      const h = new Headers(init?.headers);
      calls.push({ url: String(input), key: h.get("X-API-KEY") || "" });
      return new Response('{"ok":true}', { status: 200, headers: { "Content-Type": "application/json" } });
    }) as typeof fetch;
    sessionToken = (await mint({ secret: SESSION, challengePassed: true })) as string;
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
  });

  const env = { BACKEND_API_KEY: MASTER, SESSION_SECRET: SESSION };

  // [label, method, path, credential, expectStatus, expectForwarded]
  const ROWS: Array<[string, string, string, "anon" | "token" | "master", number, boolean]> = [
    // Reads: credential-agnostic, always forwarded (key injected server-side).
    ["read GET /api/news x anon",            "GET",  "/api/news",              "anon",   200, true],
    ["read GET /api/news x token",           "GET",  "/api/news",              "token",  200, true],
    ["read GET /api/config x anon",          "GET",  "/api/config",            "anon",   200, true],
    ["read GET /api/knowledge x anon",       "GET",  "/api/knowledge",         "anon",   200, true],
    // Legitimate writes (session-scoped): anon -> 401, token -> forwarded, master -> forwarded.
    ["write POST /api/config x anon",        "POST", "/api/config",            "anon",   401, false],
    ["write POST /api/config x token",       "POST", "/api/config",            "token",  200, true],
    ["write POST /api/config x master",      "POST", "/api/config",            "master", 200, true],
    ["write POST /api/healing/pulse x anon", "POST", "/api/healing/pulse",     "anon",   401, false],
    ["write POST /api/healing/pulse x token","POST", "/api/healing/pulse",     "token",  200, true],
    ["write POST /api/healing/pulse x master","POST","/api/healing/pulse",     "master", 200, true],
    // Sensitive actions: master-key-only. A token NEVER satisfies them.
    ["sensitive POST /api/agent/kill x anon",  "POST", "/api/agent/kill",      "anon",   401, false],
    ["sensitive POST /api/agent/kill x token", "POST", "/api/agent/kill",      "token",  401, false],
    ["sensitive POST /api/agent/kill x master","POST", "/api/agent/kill",      "master", 200, true],
    ["sensitive POST /api/agent/reset x anon", "POST", "/api/agent/reset",     "anon",   401, false],
    ["sensitive POST /api/agent/reset x token","POST", "/api/agent/reset",     "token",  401, false],
    ["sensitive POST /api/agent/reset x master","POST","/api/agent/reset",     "master", 200, true],
    // Betting writes stay master-key-only (token never covers money paths).
    ["money POST /api/betting/status x anon",  "POST", "/api/betting/status",  "anon",   401, false],
    ["money POST /api/betting/status x token", "POST", "/api/betting/status",  "token",  401, false],
    ["money POST /api/betting/status x master","POST", "/api/betting/status",  "master", 200, true],
    // Tasks family (guarded since harden-pages-functions task 1.1: normalized
    // prefixes cover the bare family root). Master-key-only like betting —
    // a session token never satisfies it.
    ["tasks POST /api/tasks x anon",   "POST", "/api/tasks",           "anon",   401, false],
    ["tasks POST /api/tasks x token",  "POST", "/api/tasks",           "token",  401, false],
    ["tasks POST /api/tasks x master", "POST", "/api/tasks",           "master", 200, true],
  ];

  for (const [label, method, path, cred, wantStatus, wantForward] of ROWS) {
    it(label, async () => {
      const opts = cred === "token" ? { token: sessionToken } : cred === "master" ? { key: MASTER } : {};
      const res = await mod.onRequest(makeCtx(makeRequest(method, path, opts), env));
      assert.equal(res.status, wantStatus, label);
      assert.equal(calls.length, wantForward ? 1 : 0, `${label}: forward count`);
      if (wantForward) assert.equal(calls[0].key, MASTER, `${label}: master key injected`);
    });
  }
});

describe("proxy hardening (harden-pages-functions)", () => {
  let calls: number;
  let realFetch: typeof fetch;

  beforeEach(async () => {
    if (!mod) {
      mod = (await import(new URL("../functions/api/%5B%5Bcatchall%5D%5D.ts", import.meta.url).href)) as unknown as { onRequest: OnRequest };
    }
    realFetch = globalThis.fetch;
    calls = 0;
    (globalThis as unknown as { fetch: typeof fetch }).fetch = (async () => {
      calls++;
      throw new TypeError("fetch failed (simulated dead origin)");
    }) as typeof fetch;
  });

  afterEach(() => {
    globalThis.fetch = realFetch;
  });

  it("dead Modal upstream -> structured 502 envelope, not a crash", async () => {
    const res = await mod.onRequest(makeCtx(makeRequest("GET", "/api/news"), { BACKEND_API_KEY: MASTER }));
    assert.equal(res.status, 502);
    const body = (await res.json()) as { error?: string; upstream?: string; retryable?: boolean };
    assert.equal(body.error, "Upstream unavailable");
    assert.equal(body.upstream, "modal");
    assert.equal(body.retryable, true);
    assert.equal(res.headers.get("Retry-After"), "5");
    assert.equal(calls, 1); // primary leg only; no worker fallback for Modal paths
  });

  it("dead worker + dead Modal -> envelope names both, fallback leg bounded", async () => {
    const res = await mod.onRequest(makeCtx(makeRequest("GET", "/api/health"), { BACKEND_API_KEY: MASTER }));
    assert.equal(res.status, 502);
    const body = (await res.json()) as { upstream?: string };
    assert.equal(body.upstream, "worker+modal");
    assert.equal(calls, 2); // both legs attempted, neither escaped as a throw
  });
});

describe("bounded rate store (harden-pages-functions 1.4)", () => {
  it("enforces the window and never exceeds the hard key cap", async () => {
    const { hitRate, RATE_STORE_CAP } = await import("../functions/lib/rate-limit.ts");
    // Window semantics: max 5 per window, 6th hit is over.
    const win = new Map<string, import("../functions/lib/rate-limit.ts").RateEntry>();
    for (let i = 0; i < 5; i++) assert.equal(hitRate(win, "1.2.3.4", 5, 60_000), false);
    assert.equal(hitRate(win, "1.2.3.4", 5, 60_000), true);
    // Cap semantics: a store filled with live entries evicts instead of growing.
    const full = new Map<string, import("../functions/lib/rate-limit.ts").RateEntry>();
    for (let i = 0; i < RATE_STORE_CAP; i++) hitRate(full, `k${i}`, 1, 3_600_000);
    assert.equal(full.size, RATE_STORE_CAP);
    hitRate(full, "one-more", 1, 3_600_000); // triggers oldest-expiry eviction
    assert.ok(full.size <= RATE_STORE_CAP, `store must stay bounded, got ${full.size}`);
  });
});
