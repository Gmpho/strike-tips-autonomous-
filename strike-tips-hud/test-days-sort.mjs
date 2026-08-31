// Standalone sort-comparator test for the new daysSinceRun column.
// Mirrors the logic in src/components/RaceCard.tsx (sortValue / sort comparator).
// Goal: document and lock the contract that "absent daysSinceRun sorts last".

const sortValue = (r, key) => {
  switch (key) {
    case "name":
      return (r.name || "").toLowerCase();
    case "daysSinceRun":
      return typeof r.daysSinceRun === "number" ? r.daysSinceRun : Number.POSITIVE_INFINITY;
    default:
      return 0;
  }
};

const isMissingForSort = (r, key) => {
  if (key === "daysSinceRun") return typeof r.daysSinceRun !== "number";
  return false;
};

const compare = (a, b, key, dir) => {
  const aMissing = isMissingForSort(a, key);
  const bMissing = isMissingForSort(b, key);
  if (aMissing && bMissing) return 0;
  if (aMissing) return 1;
  if (bMissing) return -1;
  const va = sortValue(a, key);
  const vb = sortValue(b, key);
  let cmp;
  if (typeof va === "number" && typeof vb === "number") cmp = va - vb;
  else cmp = String(va).localeCompare(String(vb));
  return cmp * dir;
};

let pass = 0, fail = 0;
const assert = (cond, label) => {
  if (cond) { pass++; }
  else { fail++; console.error("  FAIL:", label); }
};

// Fixture: typical Scottsville R1 with 4 runners, one missing daysSinceRun
const R = [
  { name: "Task Force", daysSinceRun: 16 },
  { name: "Diaval", daysSinceRun: 21 },
  { name: "Eye On The Victory", daysSinceRun: undefined },
  { name: "My China", daysSinceRun: 7 },
];

console.log("daysSinceRun sort (asc) — absent sorts last");
const asc = [...R].sort((a, b) => compare(a, b, "daysSinceRun", 1));
assert(asc[0].name === "My China", "first is smallest=7");
assert(asc[1].name === "Task Force", "second is 16");
assert(asc[2].name === "Diaval", "third is 21");
assert(asc[3].name === "Eye On The Victory", "last is absent (POSITIVE_INFINITY)");

console.log("daysSinceRun sort (desc) — absent STILL sorts last");
const desc = [...R].sort((a, b) => compare(a, b, "daysSinceRun", -1));
assert(desc[0].name === "Diaval", "first is largest=21");
assert(desc[1].name === "Task Force", "second is 16");
assert(desc[2].name === "My China", "third is 7");
assert(desc[3].name === "Eye On The Victory", "absent still last on desc");

console.log("name sort unchanged");
const byName = [...R].sort((a, b) => compare(a, b, "name", 1));
assert(byName[0].name === "Diaval", "alpha-first");
assert(byName[3].name === "Task Force", "alpha-last");

console.log(`\n${pass} passed, ${fail} failed`);
if (fail > 0) process.exit(1);