// Snapshot times are UTC walls; the card must show the SA clock face.
// Run: node --test tests/race-time.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { offTimeLocal } from "../src/lib/race-time.ts";

describe("offTimeLocal", () => {
  it("shifts the UTC wall to SA time", () => {
    // The three verified cases from 13 Nov 2026.
    assert.equal(offTimeLocal("10:10"), "12:10"); // Fairview R1
    assert.equal(offTimeLocal("14:37"), "16:37"); // Greyville R1
    assert.equal(offTimeLocal("14:15"), "16:15"); // Bahrain R1
  });

  it("wraps past midnight", () => {
    assert.equal(offTimeLocal("23:30"), "01:30");
    assert.equal(offTimeLocal("22:00"), "00:00");
  });

  it("keeps midnight and noon straight", () => {
    assert.equal(offTimeLocal("00:00"), "02:00");
    assert.equal(offTimeLocal("12:00"), "14:00");
  });

  it("normalises single-digit hours", () => {
    assert.equal(offTimeLocal("9:05"), "11:05");
  });

  it("returns anything it cannot parse untouched", () => {
    // An honest blank beats an invented time.
    assert.equal(offTimeLocal(""), "");
    assert.equal(offTimeLocal(null), "");
    assert.equal(offTimeLocal(undefined), "");
    assert.equal(offTimeLocal("TBA"), "TBA");
    assert.equal(offTimeLocal("25:00"), "25:00");
    assert.equal(offTimeLocal("12:75"), "12:75");
    assert.equal(offTimeLocal("12:10 SAST"), "12:10 SAST");
  });
});
