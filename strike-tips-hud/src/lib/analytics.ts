// Analytics transforms: store shapes -> ApexCharts-ready series.
// All functions are pure and null-safe (empty input -> empty output).

export interface SettledBet {
  track: string;
  odds: number;
  stake: number;
  payout: number;
  won: boolean;
  placedAt: string;
  /** Paper simulation ticket. Never averaged with real money. */
  isPaper: boolean;
  /** Runner / pool label ("PICK 6:3-4-5-6-7-8", "Uncle Sam", …). */
  label: string;
}

export interface BetLike {
  track?: string;
  odds?: number;
  stake?: number;
  payout?: number;
  won?: boolean;
  settled?: boolean;
  placedAt?: string;
  horse?: string;
  status?: string;
  is_paper?: boolean;
}

export function settledBets(history: BetLike[] | undefined | null): SettledBet[] {
  if (!Array.isArray(history)) return [];
  return history
    .filter((b) => b && b.settled)
    .map((b) => ({
      track: String(b.track || 'unknown'),
      odds: Number(b.odds) || 0,
      stake: Number(b.stake) || 0,
      payout: Number(b.payout) || 0,
      won: b.won === true || String(b.status || '').toUpperCase() === 'WON',
      placedAt: String(b.placedAt || ''),
      isPaper: b.is_paper === true,
      label: String(b.horse || ''),
    }));
}

/** Split a settled set by book. `real` excludes paper, never the reverse mix. */
export function byBook(bets: SettledBet[], book: 'real' | 'paper' | 'all'): SettledBet[] {
  if (book === 'all') return bets;
  return bets.filter((b) => (book === 'paper' ? b.isPaper : !b.isPaper));
}

export function betNet(b: SettledBet): number {
  return b.payout - b.stake;
}

function dayKey(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'unknown';
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

/** Per-day net P&L + running cumulative, sorted ascending. */
export function dailyPnl(bets: SettledBet[]): { day: string; net: number; cumulative: number }[] {
  const byDay = new Map<string, number>();
  for (const b of bets) {
    const k = dayKey(b.placedAt);
    if (k === 'unknown') continue;
    byDay.set(k, (byDay.get(k) || 0) + betNet(b));
  }
  const days = [...byDay.keys()].sort();
  let run = 0;
  return days.map((day) => {
    run += byDay.get(day) || 0;
    return { day, net: Math.round((byDay.get(day) || 0) * 100) / 100, cumulative: Math.round(run * 100) / 100 };
  });
}

/** Max drawdown of an equity series (peak-to-trough RAND drop + pct). */
export function maxDrawdown(balances: number[]): { amount: number; pct: number; peakIdx: number; troughIdx: number } {
  let peak = -Infinity;
  let peakIdx = 0;
  let best = { amount: 0, pct: 0, peakIdx: 0, troughIdx: 0 };
  balances.forEach((v, i) => {
    if (v > peak) {
      peak = v;
      peakIdx = i;
    }
    const dd = peak - v;
    if (dd > best.amount) {
      best = { amount: dd, pct: peak > 0 ? (dd / peak) * 100 : 0, peakIdx, troughIdx: i };
    }
  });
  return best;
}

/** Win/loss streaks (current + best). */
export function streaks(bets: SettledBet[]): { current: number; bestWin: number; bestLoss: number } {
  const ordered = [...bets].sort((a, b) => String(a.placedAt).localeCompare(String(b.placedAt)));
  let cur = 0;
  let bestWin = 0;
  let bestLoss = 0;
  for (const b of ordered) {
    cur = b.won ? (cur >= 0 ? cur + 1 : 1) : cur <= 0 ? cur - 1 : -1;
    if (cur > 0) bestWin = Math.max(bestWin, cur);
    if (cur < 0) bestLoss = Math.max(bestLoss, -cur);
  }
  return { current: cur, bestWin, bestLoss };
}

export const ODDS_BRACKETS = [
  { key: 'odds_under_2', label: '< 2.0', test: (o: number) => o > 0 && o < 2 },
  { key: 'odds_2_to_4', label: '2–4', test: (o: number) => o >= 2 && o < 4 },
  { key: 'odds_4_to_7', label: '4–7', test: (o: number) => o >= 4 && o < 7 },
  { key: 'odds_7_plus', label: '7+', test: (o: number) => o >= 7 },
] as const;

export function bracketForOdds(o: number): string {
  for (const b of ODDS_BRACKETS) {
    if (b.test(o)) return b.key;
  }
  return 'odds_2_to_4';
}

// ── Pool tickets vs win market ───────────────────────────────────
// A PICK 6 / BIPOT / JACKPOT ticket is priced as a dividend and the recorder
// labels it with a colon ("PICK 6:3-4-5-6-7-8", "EXACTA:7"). Those tickets
// return 500x-4,600x when they land and zero otherwise, so leaving them in a
// track's cell makes one jackpot look like a track edge.
//
// The label is the signal, not the odds: on the live ledger 8 pool tickets
// are priced under 100 and 4 genuine win-market longshots are priced over it
// (Flower Burst 91.0, Three Tigers 34.0, …). Classifying by odds alone would
// reclassify both groups the wrong way round.
export const WIN_MARKET_MAX_ODDS = 100;

export function isPoolTicket(b: { odds: number; label?: string }): boolean {
  const label = String(b.label || '');
  // Only fall back to the price when the ledger row has no label at all.
  return label ? label.includes(':') : Math.abs(b.odds) >= WIN_MARKET_MAX_ODDS;
}

export function poolName(label: string): string {
  const head = String(label || '').split(':')[0].trim().toUpperCase();
  return head || 'POOL';
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = sorted.length >> 1;
  return sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

export interface ExoticRow {
  pool: string;
  n: number;
  wins: number;
  staked: number;
  returned: number;
  roi: number;
  /** Median return multiple — 0 means the median pool ticket returns nothing. */
  medianMultiple: number;
  topReturn: number;
  /** Share of the book's total return this pool produced. */
  returnShare: number;
}

/** Pool-ticket performance, split by pool type (the lottery, stated plainly). */
export function exoticBreakdown(bets: SettledBet[]): ExoticRow[] {
  const pools = bets.filter(isPoolTicket);
  const gross = pools.reduce((s, b) => s + b.payout, 0);
  const groups = new Map<string, SettledBet[]>();
  for (const b of pools) {
    const key = poolName(b.label);
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(b);
  }
  return [...groups.entries()]
    .map(([pool, rows]) => {
      const staked = rows.reduce((s, b) => s + b.stake, 0);
      const returned = rows.reduce((s, b) => s + b.payout, 0);
      return {
        pool,
        n: rows.length,
        wins: rows.filter((b) => b.won).length,
        staked: Math.round(staked * 100) / 100,
        returned: Math.round(returned * 100) / 100,
        roi: staked > 0 ? Math.round(((returned - staked) / staked) * 1000) / 10 : 0,
        medianMultiple:
          Math.round(
            median(rows.filter((b) => b.stake > 0).map((b) => b.payout / b.stake)) * 100,
          ) / 100,
        topReturn: Math.round(Math.max(...rows.map((b) => b.payout)) * 100) / 100,
        returnShare: gross > 0 ? Math.round((returned / gross) * 1000) / 10 : 0,
      };
    })
    .sort((a, b) => b.returned - a.returned);
}

/** ROI% per odds bracket computed from settled history (fallback-safe). */
export function bracketRoi(
  bets: SettledBet[],
  winMarketOnly = false,
): Record<string, { roi: number; wins: number; total: number; staked: number; net: number }> {
  const out: Record<string, { roi: number; wins: number; total: number; staked: number; net: number }> = {};
  for (const b of ODDS_BRACKETS) {
    out[b.key] = { roi: 0, wins: 0, total: 0, staked: 0, net: 0 };
  }
  for (const b of bets) {
    if (winMarketOnly && isPoolTicket(b)) continue;
    const cell = out[bracketForOdds(b.odds)];
    cell.total += 1;
    if (b.won) cell.wins += 1;
    cell.staked += b.stake;
    cell.net += betNet(b);
  }
  for (const k of Object.keys(out)) {
    const c = out[k];
    c.roi = c.staked > 0 ? (c.net / c.staked) * 100 : 0;
  }
  return out;
}

export const HEATMAP_MIN_SAMPLE = 5;

/**
 * Median ROI% heatmap: top-N tracks by volume × odds brackets.
 *
 * Median, not mean: one R33,222 BIPOT in a cell of 175 tickets moves the mean
 * from -43% to +1,540%. The median ticket in most 7+ cells returns zero.
 * Cells with fewer than `minSample` tickets are blank — a +65% cell built on
 * one winner is noise, not a finding.
 */
export function roiHeatmap(
  bets: SettledBet[],
  maxTracks = 6,
  minSample = HEATMAP_MIN_SAMPLE,
): {
  tracks: string[];
  brackets: string[];
  matrix: (number | null)[][];
  volumes: number[][];
  winners: number[][];
  minSample: number;
} {
  // Win market only: pool dividends are a different question and drown the
  // column with 74-90% zeros plus a handful of 4-digit multiples.
  const market = bets.filter((b) => !isPoolTicket(b) && b.odds > 0);
  const byTrack = new Map<string, SettledBet[]>();
  for (const b of market) {
    const t = b.track.toLowerCase();
    if (!byTrack.has(t)) byTrack.set(t, []);
    byTrack.get(t)!.push(b);
  }
  const ranked = [...byTrack.entries()]
    .map(([t, bs]) => ({ t, n: bs.length }))
    .sort((a, b) => b.n - a.n)
    .slice(0, maxTracks);
  const brackets = ODDS_BRACKETS.map((b) => b.label);
  const matrix: (number | null)[][] = [];
  const volumes: number[][] = [];
  const winners: number[][] = [];
  for (const { t } of ranked) {
    const row: (number | null)[] = [];
    const vol: number[] = [];
    const won: number[] = [];
    const bs = byTrack.get(t)!;
    for (const br of ODDS_BRACKETS) {
      const cell = bs.filter((b) => br.test(b.odds));
      vol.push(cell.length);
      won.push(cell.filter((b) => b.won).length);
      if (cell.length < minSample) {
        row.push(null);
        continue;
      }
      // Median return multiple → ROI%. Stake-weighted means are what lied.
      const multiple = median(cell.filter((b) => b.stake > 0).map((b) => b.payout / b.stake));
      row.push(Math.round((multiple - 1) * 1000) / 10);
    }
    matrix.push(row);
    volumes.push(vol);
    winners.push(won);
  }
  return {
    tracks: ranked.map((r) => r.t.charAt(0).toUpperCase() + r.t.slice(1)),
    brackets,
    matrix,
    volumes,
    winners,
    minSample,
  };
}

/** Per-bet net histogram buckets (labels + counts + net sums). */
export function pnlHistogram(bets: SettledBet[]): { labels: string[]; counts: number[]; nets: number[] } {
  const edges = [-Infinity, -200, -100, -50, -20, 0, 20, 50, 100, 200, 500, Infinity];
  const labels = ['< -200', '-200…-100', '-100…-50', '-50…-20', '-20…0', '0…20', '20…50', '50…100', '100…200', '200…500', '500+'];
  const counts = new Array(labels.length).fill(0);
  const nets = new Array(labels.length).fill(0);
  for (const b of bets) {
    const v = betNet(b);
    let i = edges.length - 2;
    for (let k = 0; k < edges.length - 1; k++) {
      if (v >= edges[k] && v < edges[k + 1]) {
        i = k;
        break;
      }
    }
    counts[i] += 1;
    nets[i] = Math.round((nets[i] + v) * 100) / 100;
  }
  return { labels, counts, nets };
}

/** Compact Rand axis formatting (R1.2k). */
export function fmtRand(v: number): string {
  const a = Math.abs(v);
  if (a >= 1000) return `R${(v / 1000).toFixed(1)}k`;
  return `R${Math.round(v)}`;
}
