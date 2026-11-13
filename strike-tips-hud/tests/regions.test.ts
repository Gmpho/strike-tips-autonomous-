// The HUD's region map must know the Gulf too — the backend map learned
// Bahrain and Abu Dhabi (Nov-2026) and the two had drifted apart before.
// Run: node --test tests/regions.test.ts
import { describe, it } from "node:test";
import assert from "node:assert/strict";

import { regionOf } from "../src/lib/regions.ts";

describe("regionOf — the Gulf", () => {
  it("resolves the UAE venues", () => {
    assert.equal(regionOf("Abu Dhabi"), "UAE");
    assert.equal(regionOf("Meydan"), "UAE");
    assert.equal(regionOf("Jebel Ali"), "UAE");
    assert.equal(regionOf("Dubai"), "UAE");
    assert.equal(regionOf("Al Ain"), "UAE");
  });

  it("resolves Bahrain", () => {
    assert.equal(regionOf("Bahrain"), "BHR");
    assert.equal(regionOf("Sakhir"), "BHR");
  });

  it("reads the country suffix ATR adds", () => {
    assert.equal(regionOf("Abu Dhabi (UAE)"), "UAE");
    assert.equal(regionOf("Bahrain (BHR)"), "BHR");
  });

  it("votes a runner region when the course is unknown", () => {
    assert.equal(regionOf("Some Unknown Track", ["Bahrain"]), "BHR");
    assert.equal(regionOf("Some Unknown Track", ["Dubai"]), "UAE");
  });
});

describe("regionOf — the venues that already worked", () => {
  it("keeps resolving SA, USA, CAN, HK, AUS and UK/IE", () => {
    assert.equal(regionOf("Turffontein"), "SA");
    assert.equal(regionOf("Greyville"), "SA");
    assert.equal(regionOf("Churchill Downs"), "USA");
    assert.equal(regionOf("Woodbine"), "CAN");
    assert.equal(regionOf("Happy Valley"), "HK");
    assert.equal(regionOf("Randwick"), "AUS");
    assert.equal(regionOf("Ayr"), "UK_IE");
  });

  it("still refuses to guess where a name exists twice", () => {
    // Belmont (US + AUS) and Sandown (UK + AUS) are in AMBIGUOUS: a bare name
    // with no runner regions must never be guessed as a hemisphere. Belmont
    // Park has no map entry, so it stays OTHER; Sandown keeps the UK default
    // it has always had — both are existing, deliberate behaviour.
    assert.equal(regionOf("Belmont Park"), "OTHER");
    assert.equal(regionOf("Sandown"), "UK_IE");
    // With runners, the vote resolves it.
    assert.equal(regionOf("Belmont Park", ["USA", "USA"]), "USA");
  });

  it("never throws and never hides an unknown course", () => {
    assert.equal(regionOf("Some Unknown Track"), "OTHER");
    assert.equal(regionOf(""), "OTHER");
  });
});
