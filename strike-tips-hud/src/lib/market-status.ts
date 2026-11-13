// What can we honestly say about a race's prices?
//
// A race with runners and form but no bookmaker price is a real state — the
// Gulf meetings arrive from Betfair's form feed (ratings, pedigree, days
// since run) while prices only come from Betway, so a Gulf card can be fully
// populated and completely unpriced. Labelling that "EVALUATING" claims work
// is in progress that isn't happening, and labelling it "LIVE MARKET" is
// worse. It gets its own state instead.
//
// Run: node --test tests/market-status.test.ts

export type MarketStatusKind = 'live' | 'no-prices' | 'evaluating';

export interface MarketStatus {
  kind: MarketStatusKind;
  label: string;
  /** Tailwind colour family for the badge. */
  tone: 'emerald' | 'slate' | 'purple';
  pricedCount: number;
  runnerCount: number;
}

type Runner = { odds?: number | string | null } | null | undefined;

/** A usable price is a finite number above 1.0 (decimal odds). */
function isPriced(runner: Runner): boolean {
  if (!runner) return false;
  const raw = runner.odds;
  const n = typeof raw === 'number' ? raw : parseFloat(String(raw ?? ''));
  return Number.isFinite(n) && n > 1;
}

/**
 * Classify a race by price coverage.
 *
 * - any priced runner  -> live market
 * - runners, none priced -> no prices yet (card is real, price is absent)
 * - no runners          -> still evaluating
 */
export function marketStatus(runners: Runner[] | undefined): MarketStatus {
  const list = (runners || []).filter(Boolean) as Runner[];
  const runnerCount = list.length;
  const pricedCount = list.filter(isPriced).length;

  if (pricedCount > 0) {
    return {
      kind: 'live',
      label: 'LIVE MARKET',
      tone: 'emerald',
      pricedCount,
      runnerCount,
    };
  }
  if (runnerCount > 0) {
    return {
      kind: 'no-prices',
      label: 'NO PRICES YET',
      tone: 'slate',
      pricedCount,
      runnerCount,
    };
  }
  return {
    kind: 'evaluating',
    label: 'EVALUATING',
    tone: 'purple',
    pricedCount,
    runnerCount,
  };
}
