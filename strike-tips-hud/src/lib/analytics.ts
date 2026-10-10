// Analytics transforms: store shapes -> ApexCharts-ready series.
// All functions are pure and null-safe (empty input -> empty output).

export interface SettledBet {
  track: string;
  odds: number;
  stake: number;
  payout: number;
  won: boolean;
  placedAt: string;
}

export interface BetLike {
  track?: string;
  odds?: number;
  stake?: number;
  payout?: number;
  won?: boolean;
  settled?: boolean;
  placedAt?: string;
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
      won: b.won === true,
      placedAt: String(b.placedAt || ''),
    }));
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

/** ROI% per odds bracket computed from settled history (fallback-safe). */
export function bracketRoi(bets: SettledBet[]): Record<string, { roi: number; wins: number; total: number; staked: number; net: number }> {
  const out: Record<string, { roi: number; wins: number; total: number; staked: number; net: number }> = {};
  for (const b of ODDS_BRACKETS) {
    out[b.key] = { roi: 0, wins: 0, total: 0, staked: 0, net: 0 };
  }
  for (const b of bets) {
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

/** ROI% heatmap rows: top-N tracks by volume x odds brackets. */
export function roiHeatmap(
  bets: SettledBet[],
  maxTracks = 6,
): { tracks: string[]; brackets: string[]; matrix: (number | null)[][]; volumes: number[][] } {
  const byTrack = new Map<string, SettledBet[]>();
  for (const b of bets) {
    const t = b.track.toLowerCase();
    if (!byTrack.has(t)) byTrack.set(t, []);
    byTrack.get(t)!.push(b);
  }
  const ranked = [...byTrack.entries()]
    .map(([t, bs]) => ({ t, n: bs.length, staked: bs.reduce((s, b) => s + b.stake, 0) }))
    .sort((a, b) => b.n - a.n)
    .slice(0, maxTracks);
  const brackets = ODDS_BRACKETS.map((b) => b.label);
  const matrix: (number | null)[][] = [];
  const volumes: number[][] = [];
  for (const { t } of ranked) {
    const row: (number | null)[] = [];
    const vol: number[] = [];
    const bs = byTrack.get(t)!;
    for (const br of ODDS_BRACKETS) {
      const cell = bs.filter((b) => br.test(b.odds));
      vol.push(cell.length);
      if (cell.length === 0) {
        row.push(null);
        continue;
      }
      const staked = cell.reduce((s, b) => s + b.stake, 0);
      const net = cell.reduce((s, b) => s + betNet(b), 0);
      row.push(staked > 0 ? Math.round((net / staked) * 1000) / 10 : null);
    }
    matrix.push(row);
    volumes.push(vol);
  }
  return {
    tracks: ranked.map((r) => r.t.charAt(0).toUpperCase() + r.t.slice(1)),
    brackets,
    matrix,
    volumes,
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
