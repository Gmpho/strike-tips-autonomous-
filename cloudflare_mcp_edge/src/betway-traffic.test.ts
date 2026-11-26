import assert from "node:assert/strict";
import test from "node:test";

import {
  createTrafficFetcher,
  shouldTriggerFetch,
  TRAFFIC_FETCH_MIN_GAP_MS,
} from "./betway-traffic.ts";

function fakeCtx() {
  const pending: Promise<unknown>[] = [];
  return {
    ctx: { waitUntil: (p: Promise<unknown>) => pending.push(p) } as any,
    pending,
  };
}

function okResult() {
  return { ok: true, daily: 10, fetched: 30, failed: 0, slots: [0, 1], next: 1 };
}

test("first poll triggers, later polls inside the gap do not", () => {
  let clock = 1_000_000;
  let calls = 0;
  const trigger = createTrafficFetcher({
    now: () => clock,
    fetchBetway: async () => { calls++; return okResult(); },
  });
  const { ctx, pending } = fakeCtx();

  assert.equal(trigger({} as any, ctx, "JNB"), true);
  clock += 60_000;
  assert.equal(trigger({} as any, ctx, "JNB"), false);
  clock += 7 * 60_000;
  assert.equal(trigger({} as any, ctx, "JNB"), true);

  assert.equal(calls, 0, "the fetch is deferred via waitUntil, not awaited");
  assert.equal(pending.length, 2);
  return Promise.all(pending);
});

test("a failed fetch is logged and never rejects the request", async () => {
  let clock = 500_000;
  const logs: string[] = [];
  const trigger = createTrafficFetcher({
    now: () => clock,
    log: (line) => logs.push(line),
    fetchBetway: async () => { throw new Error("GetDaily HTTP 403"); },
  });
  const { ctx, pending } = fakeCtx();

  assert.equal(trigger({} as any, ctx, "CDG"), true);
  await Promise.all(pending);

  assert.match(logs[0], /betway-traffic-fetch failed colo=CDG.*403/);
});

test("a synchronous throw from the fetcher is also contained", async () => {
  const logs: string[] = [];
  const trigger = createTrafficFetcher({
    now: () => 1000,
    log: (line) => logs.push(line),
    fetchBetway: (() => { throw new Error("boom"); }) as any,
  });
  const { ctx, pending } = fakeCtx();

  assert.equal(trigger({} as any, ctx), true);
  await Promise.all(pending);
  assert.match(logs[0], /failed/);
});

test("shouldTriggerFetch handles first run, gap boundary and clock skew", () => {
  assert.equal(shouldTriggerFetch(1000, 0), true, "first call");
  assert.equal(shouldTriggerFetch(1000 + TRAFFIC_FETCH_MIN_GAP_MS - 1, 1000), false);
  assert.equal(shouldTriggerFetch(1000 + TRAFFIC_FETCH_MIN_GAP_MS, 1000), true);
  assert.equal(shouldTriggerFetch(500, 1000), true, "clock moved backwards");
});
