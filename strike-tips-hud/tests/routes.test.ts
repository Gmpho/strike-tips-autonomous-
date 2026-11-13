// Renaming a nav item must not break a shared URL.
//
// `Live Ops` became `Engine Ops` and moved into the operator group. `/logs`
// is bookmarked by operators, `/telemetry` is in old links, and the saved
// view in localStorage is whatever the user last clicked — all three must
// keep resolving.
//
// Run: node --test tests/routes.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { viewFromPath, VALID_VIEWS } from "../src/lib/routes.ts";

describe("viewFromPath", () => {
  it("keeps every existing path working", () => {
    for (const path of ["/logs", "/telemetry", "/dashboard", "/market-movers"]) {
      assert.equal(viewFromPath(path), path.slice(1), `${path} must still resolve`);
    }
  });

  it("routes the new /engine-ops alias to the engine view", () => {
    assert.equal(viewFromPath("/engine-ops"), "telemetry");
  });

  it("treats a trailing slash as the same view", () => {
    assert.equal(viewFromPath("/logs/"), "logs");
    assert.equal(viewFromPath("engine-ops/"), "telemetry");
  });

  it("falls back to the view the user last chose", () => {
    assert.equal(viewFromPath("/nonsense", "predictor"), "predictor");
  });

  it("never invents a view from a remembered value that no longer exists", () => {
    assert.equal(viewFromPath("/nonsense", "live-ops-removed"), "dashboard");
    assert.equal(viewFromPath("/", null), "dashboard");
  });

  it("does not let an alias smuggle in an unknown id", () => {
    assert.equal(viewFromPath("/ghost"), "dashboard");
  });

  it("every resolved view is one the app can render", () => {
    for (const path of ["/logs", "/engine-ops", "/telemetry", "/picks"]) {
      assert.ok(VALID_VIEWS.includes(viewFromPath(path)));
    }
  });
});
