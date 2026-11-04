// Unit tests for the chat edge-search helpers (chat-edge-search-cascade).
// Pure functions only — the live /mcp path is exercised by prod probes.
// Run: node --test tests/edge-search.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

describe("edge search key fallback chain", () => {
  it("prefers MCP_API_KEY, then STRIKE_TIPS_API_KEY, then BACKEND_API_KEY", async () => {
    const { edgeSearchKey } = await import("../functions/lib/edge-search.ts");
    assert.equal(edgeSearchKey({ MCP_API_KEY: "a", STRIKE_TIPS_API_KEY: "b", BACKEND_API_KEY: "c" }), "a");
    assert.equal(edgeSearchKey({ STRIKE_TIPS_API_KEY: "b", BACKEND_API_KEY: "c" }), "b");
    assert.equal(edgeSearchKey({ BACKEND_API_KEY: "c" }), "c");
    assert.equal(edgeSearchKey({}), undefined);
  });
});

describe("search context injection", () => {
  it("names the provider and caps injected results at MAX_SEARCH_RESULTS", async () => {
    const { buildSearchContext, MAX_SEARCH_RESULTS } = await import("../functions/lib/edge-search.ts");
    const bundle = {
      provider: "tavily",
      results: Array.from({ length: 8 }, (_, i) => ({ title: `T${i}`, url: `https://example.test/${i}` })),
    };
    const ctx = buildSearchContext(bundle);
    assert.equal(MAX_SEARCH_RESULTS, 5);
    assert.match(ctx, /provider: tavily/);
    assert.ok(ctx.includes("https://example.test/0"));
    assert.ok(!ctx.includes("https://example.test/5"), "sixth result must be dropped");
    assert.match(ctx, /Never invent URLs/);
  });

  it("degrades honestly when search is unavailable (null or empty)", async () => {
    const { buildSearchContext, toGroundingSources } = await import("../functions/lib/edge-search.ts");
    const cases: unknown[] = [null, { provider: "none", results: [] }];
    for (const bundle of cases) {
      const ctx = buildSearchContext(bundle as any);
      assert.match(ctx, /UNAVAILABLE/);
      assert.match(ctx, /do not invent/i);
      assert.deepEqual(toGroundingSources(bundle as any), []);
    }
  });

  it("maps title/url chips for the UI (snippet dropped)", async () => {
    const { toGroundingSources } = await import("../functions/lib/edge-search.ts");
    const out = toGroundingSources({ provider: "exa", results: [{ title: "A", url: "https://a.test", snippet: "s" }] });
    assert.deepEqual(out, [{ title: "A", url: "https://a.test" }]);
  });
});
