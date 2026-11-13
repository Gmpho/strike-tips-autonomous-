// A race with runners but no price is a real, common state — the Gulf cards
// arrive from Betfair's form feed while prices only come from Betway. It must
// never be labelled "LIVE MARKET" (nothing to be live on) or "EVALUATING"
// (no work is happening).
// Run: node --test tests/market-status.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { marketStatus } from "../src/lib/market-status.ts";

describe("marketStatus", () => {
  it("is live when at least one runner carries a usable price", () => {
    const s = marketStatus([{ odds: 3.2 }, { odds: null }, { odds: 7 }]);
    assert.equal(s.kind, "live");
    assert.equal(s.label, "LIVE MARKET");
    assert.equal(s.pricedCount, 2);
    assert.equal(s.runnerCount, 3);
  });

  it("accepts prices that arrive as strings", () => {
    assert.equal(marketStatus([{ odds: "4.5" }]).kind, "live");
  });

  it("is 'no prices yet' when the field is loaded but nothing is priced", () => {
    // The Bahrain case: 13 runners with form, ratings and pedigree, no price.
    const runners = Array.from({ length: 13 }, () => ({ odds: null }));
    const s = marketStatus(runners);
    assert.equal(s.kind, "no-prices");
    assert.equal(s.label, "NO PRICES YET");
    assert.equal(s.runnerCount, 13);
    assert.equal(s.pricedCount, 0);
  });

  it("is 'no prices yet' when odds are absent entirely", () => {
    assert.equal(marketStatus([{ name: "Royal Champion" }]).kind, "no-prices");
  });

  it("is evaluating only when there are no runners at all", () => {
    assert.equal(marketStatus([]).kind, "evaluating");
    assert.equal(marketStatus(undefined).kind, "evaluating");
    assert.equal(marketStatus(undefined).label, "EVALUATING");
  });

  it("never counts a placeholder price as a real one", () => {
    // 0, 1, negative and junk all mean "no price", not "odds of zero".
    for (const odds of [0, 1, "1.0", -3, "SP", "", "n/a", null]) {
      assert.equal(
        marketStatus([{ odds }]).kind,
        "no-prices",
        `odds=${JSON.stringify(odds)} must not count as priced`,
      );
    }
  });

  it("tolerates null runners in the array", () => {
    const s = marketStatus([null, { odds: 2.5 }, undefined]);
    assert.equal(s.kind, "live");
    assert.equal(s.runnerCount, 1);
    assert.equal(s.pricedCount, 1);
  });
});
