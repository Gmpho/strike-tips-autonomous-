// Runtime verification for the Live Ops race⨯story linker.
// Pure module, no deps — run: node --test tests/race-story-link.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { linkStoriesToRaces } from "../src/lib/race-story-link.ts";

const races = [
  {
    id: "tt.4",
    course: "Turffontein",
    raceNumber: 4,
    t: "13:20",
    runners: [{ name: "Oriental Charm" }, { name: "Eight Is Enough" }],
  },
  {
    id: "dw.1",
    course: "Durbanville",
    raceNumber: 1,
    t: "12:05",
    runners: [{ name: "Winter Solstice" }],
  },
];

const news = [
  { id: "n1", title: "Oriental Charm lights up Turffontein mile", url: "https://a/1" },
  { id: "n2", title: "Durbanville under the spotlight this weekend", url: "https://a/2" },
  { id: "n3", title: "Winter Solstice declared for the Cape Town Met", url: "https://a/3" },
  { id: "n4", title: "Bloodstock roundup from across the globe", url: "https://a/4" },
];

describe("race ⨯ story linking", () => {
  it("links a race when a story names the course", () => {
    const out = linkStoriesToRaces(races, news);
    const tt = out.find((r) => r.id === "tt.4");
    assert.ok(tt, "Turffontein race should be linked");
    assert.ok(tt.stories.some((s) => s.id === "n1"));
    assert.equal(tt.stories.find((s) => s.id === "n1")?.matchedOn, "Turffontein");
  });

  it("links a race when a story names a horse", () => {
    const out = linkStoriesToRaces(races, news);
    const dw = out.find((r) => r.id === "dw.1");
    assert.ok(dw, "Durbanville race should be linked via its horse");
    assert.ok(dw.stories.some((s) => s.id === "n3"));
    assert.equal(dw.stories.find((s) => s.id === "n3")?.matchedOn, "Winter Solstice");
  });

  it("never links an unrelated story", () => {
    const out = linkStoriesToRaces(races, news);
    const ids = out.flatMap((r) => r.stories.map((s) => s.id));
    assert.ok(!ids.includes("n4"), "generic roundup must not attach to any race");
  });

  it("respects whole-word matching (no substring false positives)", () => {
    const out = linkStoriesToRaces(races, [
      { id: "x1", title: "Turffonteiners head to the Cape" },
    ]);
    assert.equal(out.length, 0, "'Turffonteiners' must not match 'Turffontein'");
  });

  it("ignores very short horse names", () => {
    const out = linkStoriesToRaces(
      [{ id: "r", course: "Kenilworth", raceNumber: 2, t: "14:00", runners: [{ name: "El" }] }],
      [{ id: "x", title: "El pops at Kenilworth" }],
    );
    // 'El' is below the minimum length — the link must come from the course.
    const only = out[0];
    assert.ok(only);
    assert.equal(only.stories[0].matchedOn, "Kenilworth");
  });

  it("caps stories per race and sorts most-linked races first", () => {
    const many = Array.from({ length: 6 }, (_, i) => ({
      id: `t${i}`,
      title: `Turffontein roundup part ${i}`,
    }));
    const out = linkStoriesToRaces(races, many, { maxStoriesPerRace: 2 });
    assert.equal(out[0].id, "tt.4");
    assert.equal(out[0].stories.length, 2, "per-race cap must hold");
  });

  it("caps the number of races", () => {
    const lots = Array.from({ length: 30 }, (_, i) => ({
      id: `t${i}`,
      course: `Track${i}`,
      raceNumber: 1,
      t: "10:00",
      runners: [{ name: `Horse${i}` }],
    }));
    const news2 = lots.map((r) => ({ id: `n-${r.id}`, title: `${r.course} preview` }));
    const out = linkStoriesToRaces(lots, news2, { maxRaces: 5 });
    assert.equal(out.length, 5);
  });

  it("handles empty inputs safely", () => {
    assert.deepEqual(linkStoriesToRaces([], news), []);
    assert.deepEqual(linkStoriesToRaces(races, []), []);
    assert.deepEqual(linkStoriesToRaces(undefined as any, news), []);
  });
});
