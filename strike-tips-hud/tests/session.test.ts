// Zero-dependency tests for functions/lib/session.ts (Node built-in runner).
// Run: node --test tests/session.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  mint,
  verify,
  matches,
  scopeAllows,
  base64urlEncode,
  base64urlDecode,
  SESSION_TTL_SECS,
  CLOCK_SKEW_SECS,
} from "../functions/lib/session.ts";

const SECRET = "test-secret-for-unit-tests-only";

describe("mint issuance gating (task 1.2)", () => {
  it("mints only after a passed challenge", async () => {
    const ok = await mint({ secret: SECRET, challengePassed: true });
    assert.ok(typeof ok === "string" && ok.includes("."));
    assert.equal(await mint({ secret: SECRET, challengePassed: false }), null);
  });
  it("fail-closed on empty secret or empty audience", async () => {
    assert.equal(await mint({ secret: "", challengePassed: true }), null);
    assert.equal(await mint({ secret: SECRET, aud: "", challengePassed: true }), null);
  });
});

describe("verify + TTL/audience (task 1.3)", () => {
  it("round-trips a fresh token", async () => {
    const t = await mint({ secret: SECRET, challengePassed: true });
    assert.ok(t);
    const c = await verify({ secret: SECRET, token: t! });
    assert.ok(c && c.aud === "hud-write" && c.exp - c.iat === SESSION_TTL_SECS);
  });
  it("rejects expired tokens and issues fresh ones on renewal", async () => {
    const t = await mint({ secret: SECRET, challengePassed: true, nowSecs: 1000 });
    assert.ok(t);
    assert.equal(await verify({ secret: SECRET, token: t!, nowSecs: 1000 + SESSION_TTL_SECS + 1 }), null);
    const fresh = await mint({ secret: SECRET, challengePassed: true, nowSecs: 1000 + SESSION_TTL_SECS + 1 });
    assert.ok(fresh && await verify({ secret: SECRET, token: fresh!, nowSecs: 1000 + SESSION_TTL_SECS + 1 }));
  });
  it("rejects wrong audience", async () => {
    const t = await mint({ secret: SECRET, challengePassed: true, aud: "hud-write" });
    assert.ok(t);
    assert.equal(await verify({ secret: SECRET, token: t!, aud: "other" }), null);
  });
  it("rejects tokens issued in the future beyond clock skew", async () => {
    const t = await mint({ secret: SECRET, challengePassed: true, nowSecs: 100000 });
    assert.ok(t);
    assert.equal(await verify({ secret: SECRET, token: t!, nowSecs: 1000 }), null);
  });
  it("rejects tampering and malformed tokens", async () => {
    const t = await mint({ secret: SECRET, challengePassed: true });
    assert.ok(t);
    const [p, s] = t!.split(".");
    assert.equal(await verify({ secret: SECRET, token: p + "." + s.slice(0, -2) + "AA" }), null);
    assert.equal(await verify({ secret: SECRET, token: "junk" }), null);
    assert.equal(await verify({ secret: SECRET, token: "" }), null);
    assert.equal(await verify({ secret: "wrong", token: t! }), null);
  });
});

describe("matches boundary helper", () => {
  it("exact and boundary-aware prefix matching", () => {
    assert.equal(matches("/api/config", "/api/config"), true);
    assert.equal(matches("/api/config/x", "/api/config"), true);
    assert.equal(matches("/api/configx", "/api/config"), false);
    assert.equal(matches("/api/tasks", "/api/tasks/"), false); // known sibling-change hole
    assert.equal(matches("/api/tasks/", "/api/tasks/"), true);
  });
});

describe("scopeAllows (kill/reset negative)", () => {
  it("allows legitimate write families", () => {
    assert.equal(scopeAllows("/api/config"), true);
    assert.equal(scopeAllows("/api/config/test_telegram"), true);
    assert.equal(scopeAllows("/api/healing/pulse"), true);
    assert.equal(scopeAllows("/api/dreaming/pulse"), true);
  });
  it("denies sensitive actions first and independently", () => {
    assert.equal(scopeAllows("/api/agent/kill"), false);
    assert.equal(scopeAllows("/api/agent/kill/__canary__"), false);
    assert.equal(scopeAllows("/api/agent/reset"), false);
    assert.equal(scopeAllows("/api/agent/reset/__canary__"), false);
    assert.equal(scopeAllows("/api/news"), false);
    assert.equal(scopeAllows("/api/chat"), false);
  });
});

describe("base64url edges", () => {
  it("round-trips and rejects bad padding", async () => {
    const b = new Uint8Array([0, 1, 2, 250, 255]);
    assert.deepEqual(base64urlDecode(base64urlEncode(b)), b);
    assert.equal(base64urlDecode("abcde"), null); // len % 4 === 1
  });
});
