// Unit tests for the ai-spend-guard primitives (harden-pages-functions).
// Pure functions and constants only — no network, no WebSocket.
// Run: node --test tests/spend-guard.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("live frame throttle (2.2)", () => {
  it("allows the burst, then drops until tokens refill", async () => {
    const { makeFrameThrottle } = await import("../functions/api/live.ts");
    const allow = makeFrameThrottle(80, 10); // small burst for testability
    for (let i = 0; i < 10; i++) assert.equal(allow(), true, `burst frame ${i} must pass`);
    assert.equal(allow(), false, "frame beyond burst must be dropped");
    assert.equal(allow(), false, "immediate second frame must also be dropped");
  });

  it("refills at the configured rate over time", async () => {
    const { makeFrameThrottle } = await import("../functions/api/live.ts");
    const allow = makeFrameThrottle(1000, 2); // 1000/s => ~1 token per ms, bucket holds 2
    assert.equal(allow(), true);
    assert.equal(allow(), true);
    assert.equal(allow(), false); // bucket drained
    await new Promise((r) => setTimeout(r, 8)); // ~8 tokens accrued, capped at burst=2
    let passed = 0;
    for (let i = 0; i < 5; i++) if (allow()) passed++;
    assert.equal(passed, 2, "refill must restore exactly the burst capacity");
  });
});

describe("chat per-call caps are pinned (2.3)", () => {
  it("keeps the documented body and token ceilings", async () => {
    const mod = (await import("../functions/api/chat.ts")) as unknown as {
      MAX_BODY_BYTES: number;
      MAX_TOKENS: number;
    };
    assert.equal(mod.MAX_BODY_BYTES, 32_768, "32 KB body cap must not drift");
    assert.equal(mod.MAX_TOKENS, 1500, "max_tokens cap must not drift");
  });
});