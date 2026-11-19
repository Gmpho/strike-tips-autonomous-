// Banking-grade analytics suite (ApexCharts, lazy-loaded chunk).
// Data comes from the HUD store via props — no fetching here.
import React from 'react';
import type { ApexOptions } from 'apexcharts';
import { ApexChart } from './ApexChart';
import {
  APEX_ACCENT,
  APEX_DOWN,
  APEX_UP,
  apexBase,
  randAxis,
} from './apex-theme';
import {
  ODDS_BRACKETS,
  bracketRoi,
  dailyPnl,
  exoticBreakdown,
  fmtRand,
  maxDrawdown,
  pnlHistogram,
  roiHeatmap,
  settledBets,
  type BetLike,
} from '../../lib/analytics';

export interface BankrollPoint {
  t: string;
  balance: number;
}

function Card({ title, right, children }: { title: string; right?: React.ReactNode; children: React.ReactNode }) {
  return (
    <div className="p-4 sm:p-6 rounded-2xl bg-theme-panel border border-theme">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">{title}</h3>
        {right}
      </div>
      {children}
    </div>
  );
}

// ── 1. Equity curve ──────────────────────────────────────────────
export const EquityChart: React.FC<{ history: BankrollPoint[] }> = React.memo(({ history }) => {
  const { series, options, head, tail } = React.useMemo(() => {
    // Backend seeds the series with a non-date "Start" anchor — map any
    // unparseable timestamp to the day before the first real point so the
    // datetime axis never chokes (Sep-2026: whole curve failed to render).
    const dated = history.map((p) => ({ t: Date.parse(p.t), balance: p.balance }));
    const firstValid = dated.find((d) => !Number.isNaN(d.t));
    const base = (firstValid ? firstValid.t : Date.now()) - 86400000;
    const data = dated.map((d) => ({
      x: Number.isNaN(d.t) ? base : d.t,
      y: Math.round(d.balance * 100) / 100,
    }));
    const balances = history.map((p) => p.balance);
    const up = balances[balances.length - 1] >= balances[0];
    const color = up ? APEX_UP : APEX_DOWN;
    const dd = maxDrawdown(balances);
    const troughT = history[dd.troughIdx]?.t;
    const options: ApexOptions = {
      ...apexBase,
      chart: { ...apexBase.chart, zoom: { enabled: true } },
      colors: [color],
      fill: {
        type: 'gradient',
        gradient: { shadeIntensity: 1, opacityFrom: 0.35, opacityTo: 0.02, stops: [0, 100] },
      },
      stroke: { curve: 'smooth', width: 2.5 },
      markers: { size: 0, hover: { size: 5 } },
      xaxis: { type: 'datetime', labels: { datetimeUTC: false }, tooltip: { enabled: false } },
      yaxis: randAxis(),
      tooltip: {
        ...apexBase.tooltip,
        x: { format: 'dd MMM HH:mm' },
        y: { formatter: (v: number) => `R ${v.toLocaleString([], { minimumFractionDigits: 2 })}` },
      },
      annotations:
        dd.amount > 0
          ? {
              points: [
                {
                  x: troughT as never,
                  y: balances[dd.troughIdx],
                  marker: { size: 4, fillColor: APEX_DOWN, strokeColor: '#0c0817', strokeWidth: 2 },
                  label: {
                    text: `Max DD −${fmtRand(dd.amount)}`,
                    borderColor: APEX_DOWN,
                    style: { color: '#fff', background: APEX_DOWN, fontSize: '10px' },
                  },
                },
              ],
            }
          : undefined,
    };
    return {
      series: [{ name: 'Balance', data }],
      options,
      head: balances[0],
      tail: balances[balances.length - 1],
    };
  }, [history]);

  if (history.length < 2) return null;
  const up = tail >= head;
  return (
    <Card
      title="Equity Curve"
      right={
        <span className={`text-xs font-black tabular ${up ? 'text-emerald-400' : 'text-red-400'}`}>
          R{head.toFixed(0)} → R{tail.toFixed(0)}
        </span>
      }
    >
      <ApexChart type="area" series={series} options={options} height={260} />
    </Card>
  );
});
EquityChart.displayName = 'EquityChart';

// ── 2. Daily P&L bars + cumulative line ──────────────────────────
export const DailyPnlChart: React.FC<{ bets: BetLike[] }> = React.memo(({ bets }) => {
  const { series, options, empty } = React.useMemo(() => {
    const days = dailyPnl(settledBets(bets));
    if (days.length === 0) return { series: [], options: {}, empty: true as const };
    const options: ApexOptions = {
      ...apexBase,
      stroke: { width: [0, 3], curve: 'smooth' },
      colors: [APEX_ACCENT, APEX_UP],
      yaxis: randAxis(),
      xaxis: { type: 'datetime', labels: { datetimeUTC: false }, tooltip: { enabled: false } },
      tooltip: {
        ...apexBase.tooltip,
        shared: true,
        x: { format: 'dd MMM yyyy' },
        y: [
          { formatter: (v: number) => `${v >= 0 ? '+' : ''}R${v.toFixed(2)} (day)` },
          { formatter: (v: number) => `R${v.toFixed(2)} (total)` },
        ],
      },
      legend: { show: true, position: 'top', horizontalAlign: 'right' },
    };
    return {
      empty: false as const,
      options,
      series: [
        {
          name: 'Daily net',
          type: 'column',
          data: days.map((d) => ({
            x: d.day,
            y: d.net,
            fillColor: d.net >= 0 ? APEX_UP : APEX_DOWN,
          })),
        },
        { name: 'Cumulative', type: 'line', data: days.map((d) => ({ x: d.day, y: d.cumulative })) },
      ],
    };
  }, [bets]);

  if (empty) return null;
  return (
    <Card title="Daily P&L">
      <ApexChart type="line" series={series} options={options} height={250} />
    </Card>
  );
});
DailyPnlChart.displayName = 'DailyPnlChart';

// ── 3. ROI by track (diverging horizontal bars) ──────────────────
// `roiByTrack` should be the *capped* map: one jackpot deciding a track is
// what crowned Turffontein at +780% while it was losing money.
export const TrackRoiChart: React.FC<{
  roiByTrack: Record<string, number> | undefined;
  title?: string;
  note?: string;
}> = React.memo(({ roiByTrack, title = 'ROI by Track', note }) => {
  const { series, options, empty } = React.useMemo(() => {
    const rows = Object.entries(roiByTrack || {})
      .map(([name, roi]) => ({ name: name.charAt(0).toUpperCase() + name.slice(1), roi: Number(roi) || 0 }))
      .sort((a, b) => a.roi - b.roi);
    if (rows.length === 0) return { series: [], options: {}, empty: true as const };
    const options: ApexOptions = {
      ...apexBase,
      plotOptions: {
        bar: { horizontal: true, distributed: true, barHeight: '55%', borderRadius: 6 },
      },
      colors: rows.map((r) => (r.roi >= 0 ? APEX_UP : APEX_DOWN)),
      xaxis: { labels: { formatter: (v: number) => `${v.toFixed(0)}%` } },
      yaxis: { labels: { style: { fontWeight: 700 } } },
      tooltip: { ...apexBase.tooltip, y: { formatter: (v: number) => `${v >= 0 ? '+' : ''}${v.toFixed(1)}% ROI` } },
      legend: { show: false },
    };
    return {
      empty: false as const,
      options,
      series: [{ name: 'ROI', data: rows.map((r) => ({ x: r.name, y: Math.round(r.roi * 10) / 10 })) }],
    };
  }, [roiByTrack]);

  if (empty) return null;
  return (
    <Card
      title={title}
      right={note ? <span className="text-[10px] font-black text-theme-secondary">{note}</span> : undefined}
    >
      <ApexChart type="bar" series={series} options={options} height={Math.max(180, (series[0] as { data: unknown[] }).data.length * 44)} />
    </Card>
  );
});
TrackRoiChart.displayName = 'TrackRoiChart';

// ── 4. ROI by odds bracket (columns) ─────────────────────────────
export const BracketChart: React.FC<{ bets: BetLike[]; winMarketOnly?: boolean; title?: string }> = React.memo(
  ({ bets, winMarketOnly = false, title = 'ROI by Odds Bracket' }) => {
    const { series, options, empty } = React.useMemo(() => {
      const settled = settledBets(bets);
      if (settled.length === 0) return { series: [], options: {}, empty: true as const };
      const m = bracketRoi(settled, winMarketOnly);
      const rows = ODDS_BRACKETS.map((b) => ({ ...b, ...m[b.key] }));
      const options: ApexOptions = {
        ...apexBase,
        plotOptions: { bar: { distributed: true, borderRadius: 8, columnWidth: '55%' } },
        colors: rows.map((r) => (r.roi >= 0 ? APEX_UP : APEX_DOWN)),
        dataLabels: {
          enabled: true,
          formatter: (v: number) => `${v >= 0 ? '+' : ''}${Number(v).toFixed(0)}%`,
          offsetY: -18,
          style: { fontSize: '11px', fontWeight: 800, colors: [APEX_UP] },
        },
        xaxis: { categories: rows.map((r) => r.label), axisTicks: { show: false } },
        yaxis: { labels: { formatter: (v: number) => `${v.toFixed(0)}%` } },
        tooltip: {
          ...apexBase.tooltip,
          y: { formatter: (v: number, o: never) => {
            const i = (o as { dataPointIndex: number }).dataPointIndex;
            const r = rows[i];
            const wr = r.total > 0 ? Math.round((r.wins / r.total) * 100) : 0;
            return `${v.toFixed(1)}% · WR ${wr}% · ${r.total} bets · net R${r.net.toFixed(0)}`;
          } },
        },
        legend: { show: false },
      };
      return {
        empty: false as const,
        options,
        series: [{ name: 'ROI', data: rows.map((r) => Math.round(r.roi * 10) / 10) }],
      };
    }, [bets, winMarketOnly]);

    if (empty) return null;
    return (
      <Card title={title}>
        <ApexChart type="bar" series={series} options={options} height={270} />
      </Card>
    );
  },
);
BracketChart.displayName = 'BracketChart';

// ── 5. Win / loss donut ──────────────────────────────────────────
export const WinLossDonut: React.FC<{ wins: number; losses: number; title?: string; note?: string }> = React.memo(
  ({ wins, losses, title = 'Win / Loss', note }) => {
    const total = wins + losses;
    const options: ApexOptions = React.useMemo(
      () => ({
        ...apexBase,
        colors: [APEX_UP, APEX_DOWN],
        labels: ['Wins', 'Losses'],
        plotOptions: {
          pie: {
            donut: {
              size: '68%',
              labels: {
                show: true,
                total: {
                  show: true,
                  label: 'Win rate',
                  fontSize: '11px',
                  fontWeight: 800,
                  color: '#94a3b8',
                  formatter: () => (total > 0 ? `${((wins / total) * 100).toFixed(1)}%` : '—'),
                },
                value: { fontSize: '22px', fontWeight: 900, color: '#f1f5f9' },
              },
            },
          },
        },
        stroke: { colors: ['#0c0817'], width: 3 },
        tooltip: { ...apexBase.tooltip, y: { formatter: (v: number) => `${v} bets` } },
        legend: { show: true, position: 'bottom' },
      }),
      [wins, total],
    );
    if (total === 0) return null;
    return (
      <Card
        title={title}
        right={note ? <span className="text-[10px] font-black text-theme-secondary">{note}</span> : undefined}
      >
        <ApexChart type="donut" series={[wins, losses]} options={options} height={250} />
      </Card>
    );
  },
);
WinLossDonut.displayName = 'WinLossDonut';

// ── 6. Per-bet P&L histogram ─────────────────────────────────────
export const PnlHistogram: React.FC<{ bets: BetLike[] }> = React.memo(({ bets }) => {
  const { series, options, empty, best, worst } = React.useMemo(() => {
    const settled = settledBets(bets);
    if (settled.length === 0) return { series: [], options: {}, empty: true as const, best: 0, worst: 0 };
    const h = pnlHistogram(settled);
    const mid = 5; // buckets below index 5 are losses
    const options: ApexOptions = {
      ...apexBase,
      plotOptions: { bar: { distributed: true, borderRadius: 5, columnWidth: '70%' } },
      colors: h.labels.map((_, i) => (i < mid ? APEX_DOWN : APEX_UP)),
      xaxis: { categories: h.labels, labels: { rotate: -45, style: { fontSize: '10px' } } },
      yaxis: { title: { text: 'bets' } },
      tooltip: {
        ...apexBase.tooltip,
        y: { formatter: (v: number, o: never) => {
          const i = (o as { dataPointIndex: number }).dataPointIndex;
          return `${v} bets · net R${h.nets[i].toFixed(0)}`;
        } },
      },
      legend: { show: false },
    };
    const nets = settled.map((b) => b.payout - b.stake);
    return {
      empty: false as const,
      options,
      series: [{ name: 'Bets', data: h.counts }],
      best: Math.max(...nets),
      worst: Math.min(...nets),
    };
  }, [bets]);

  if (empty) return null;
  return (
    <Card
      title="P&L Distribution"
      right={<span className="text-[10px] font-black text-theme-secondary tabular">best +R{best.toFixed(0)} · worst R{worst.toFixed(0)}</span>}
    >
      <ApexChart type="bar" series={series} options={options} height={250} />
    </Card>
  );
});
PnlHistogram.displayName = 'PnlHistogram';

// ── 7. Track × odds ROI heatmap (median, win market, n-gated) ────
export const RoiHeatmap: React.FC<{ bets: BetLike[]; title?: string }> = React.memo(
  ({ bets, title = 'ROI Heatmap · Track × Odds' }) => {
    const { series, options, empty, minSample, sample } = React.useMemo(() => {
      const hm = roiHeatmap(settledBets(bets));
      if (hm.tracks.length === 0) {
        return { series: [], options: {}, empty: true as const, minSample: hm.minSample, sample: { cells: 0, positive: 0 } };
      }
      // State the finding in words. A grid of identical −100% cells is honest
      // but reads as a rendering fault; it is actually the answer.
      const values = hm.matrix.flat().filter((v): v is number => v !== null);
      const sample = { cells: values.length, positive: values.filter((v) => v > 0).length };
      const options: ApexOptions = {
        ...apexBase,
        plotOptions: {
          heatmap: {
            radius: 8,
            enableShades: true,
            shadeIntensity: 0.65,
            colorScale: {
              ranges: [
                { from: -100000, to: -0.01, color: APEX_DOWN, name: 'Negative' },
                { from: 0, to: 0, color: '#475569', name: 'Flat' },
                { from: 0.01, to: 100000, color: APEX_UP, name: 'Positive' },
              ],
            },
          },
        },
        colors: [APEX_UP],
        dataLabels: {
          enabled: true,
          formatter: (v: number | string) =>
            v === null || v === undefined || v === '' ? '–' : `${Number(v).toFixed(0)}%`,
          style: { fontSize: '11px', fontWeight: 800, colors: ['#f1f5f9'] },
        },
        xaxis: { categories: hm.brackets, axisTicks: { show: false } },
        tooltip: {
          ...apexBase.tooltip,
          y: {
            formatter: (v: number, o: never) => {
              const oo = o as unknown as { seriesIndex: number; dataPointIndex: number };
              const vol = hm.volumes[oo.seriesIndex]?.[oo.dataPointIndex] ?? 0;
              const won = hm.winners[oo.seriesIndex]?.[oo.dataPointIndex] ?? 0;
              // A blank cell is not 0% ROI — it is too few tickets to say.
              if (v === null || v === undefined) {
                return vol === 0
                  ? 'no settled win-market tickets'
                  : `${vol} tickets · under ${hm.minSample}, no median shown`;
              }
              return `${Number(v).toFixed(1)}% median ROI · ${vol} tickets · ${won} won`;
            },
          },
        },
        legend: { show: false },
      };
      return {
        empty: false as const,
        minSample: hm.minSample,
        sample,
        options,
        series: hm.tracks.map((t, i) => ({
          name: t,
          data: hm.brackets.map((b, j) => ({ x: b, y: hm.matrix[i][j] })),
        })),
      };
    }, [bets]);

    if (empty) return null;
    return (
      <Card
        title={title}
        right={<span className="text-[10px] font-black text-theme-secondary">median % ROI · win market</span>}
      >
        {sample.cells > 0 && (
          <p className="mb-2 text-[11px] font-bold text-theme-primary">
            {sample.cells} cell{sample.cells === 1 ? '' : 's'} with {minSample}+ settled tickets ·{' '}
            <span className={sample.positive > 0 ? 'text-emerald-400' : 'text-red-400'}>
              {sample.positive} positive
            </span>
            {sample.positive < sample.cells
              ? ` · the median ticket is a loser in ${sample.cells - sample.positive} of ${sample.cells}`
              : ''}
          </p>
        )}
        <ApexChart type="heatmap" series={series} options={options} height={260} />
        <p className="mt-3 text-[10px] leading-relaxed text-theme-secondary">
          Median ticket in the cell, not the mean — one R33,000 pool dividend in a cell of 175 turns
          −43% into +1,540%. Pool tickets (PICK 6, BIPOT, JACKPOT) are excluded here and reported
          below. Cells under {minSample} settled tickets stay blank: a triple-digit ROI from one
          winner is not a finding.
        </p>
      </Card>
    );
  },
);
RoiHeatmap.displayName = 'RoiHeatmap';

// ── 8. Pool tickets, stated plainly ──────────────────────────────
// The exotic book is where the profit in this ledger lives, and where 74-90%
// of tickets return nothing. It gets its own table so it can never be read as
// "the model is strong on outsiders".
export const ExoticsTable: React.FC<{ bets: BetLike[] }> = React.memo(({ bets }) => {
  const rows = React.useMemo(() => exoticBreakdown(settledBets(bets)), [bets]);
  if (rows.length === 0) return null;
  const totalTickets = rows.reduce((s, r) => s + r.n, 0);
  const totalWon = rows.reduce((s, r) => s + r.wins, 0);
  const totalStaked = rows.reduce((s, r) => s + r.staked, 0);
  const totalReturned = rows.reduce((s, r) => s + r.returned, 0);
  return (
    <Card
      title="Pool Tickets · the lottery, itemised"
      right={<span className="text-[10px] font-black text-theme-secondary">{totalTickets} tickets</span>}
    >
      <div className="overflow-x-auto">
        <table className="min-w-full text-xs">
          <thead>
            <tr className="text-[10px] uppercase tracking-wider text-theme-secondary">
              <th className="text-left py-2 pr-3 font-black">Pool</th>
              <th className="text-right py-2 px-2 font-black">Tickets</th>
              <th className="text-right py-2 px-2 font-black">Won</th>
              <th className="text-right py-2 px-2 font-black">Staked</th>
              <th className="text-right py-2 px-2 font-black">Returned</th>
              <th className="text-right py-2 px-2 font-black">ROI</th>
              <th className="text-right py-2 px-2 font-black">Median</th>
              <th className="text-right py-2 pl-2 font-black">% of returns</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.pool} className="border-t border-theme">
                <td className="py-2 pr-3 font-bold text-theme-primary whitespace-nowrap">{r.pool}</td>
                <td className="py-2 px-2 text-right tabular text-theme-secondary">{r.n}</td>
                <td className="py-2 px-2 text-right tabular text-theme-secondary">
                  {r.wins}
                  <span className="text-theme-secondary/60"> ({Math.round((r.wins / r.n) * 100)}%)</span>
                </td>
                <td className="py-2 px-2 text-right tabular text-theme-secondary">{fmtRand(r.staked)}</td>
                <td className="py-2 px-2 text-right tabular text-theme-primary">{fmtRand(r.returned)}</td>
                <td className={`py-2 px-2 text-right tabular font-black ${r.roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {r.roi >= 0 ? '+' : ''}{r.roi.toFixed(0)}%
                </td>
                <td className="py-2 px-2 text-right tabular text-theme-secondary">
                  {r.medianMultiple.toFixed(2)}×
                </td>
                <td className="py-2 pl-2 text-right tabular text-theme-secondary">{r.returnShare.toFixed(0)}%</td>
              </tr>
            ))}
            <tr className="border-t-2 border-theme font-black">
              <td className="py-2 pr-3 text-theme-primary">All pools</td>
              <td className="py-2 px-2 text-right tabular text-theme-primary">{totalTickets}</td>
              <td className="py-2 px-2 text-right tabular text-theme-primary">
                {totalWon}
                <span className="text-theme-secondary/60"> ({Math.round((totalWon / totalTickets) * 100)}%)</span>
              </td>
              <td className="py-2 px-2 text-right tabular text-theme-primary">{fmtRand(totalStaked)}</td>
              <td className="py-2 px-2 text-right tabular text-theme-primary">{fmtRand(totalReturned)}</td>
              <td className={`py-2 px-2 text-right tabular ${totalReturned >= totalStaked ? 'text-emerald-400' : 'text-red-400'}`}>
                {totalStaked > 0
                  ? `${totalReturned >= totalStaked ? '+' : ''}${(((totalReturned - totalStaked) / totalStaked) * 100).toFixed(0)}%`
                  : '—'}
              </td>
              <td className="py-2 px-2 text-right tabular text-theme-secondary">
                {medianOf(rows.map((r) => r.medianMultiple)).toFixed(2)}×
              </td>
              <td className="py-2 pl-2 text-right tabular text-theme-secondary">100%</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p className="mt-3 text-[10px] leading-relaxed text-theme-secondary">
        Median is the middle ticket's return multiple — 0.00× means the median pool ticket buys
        nothing. Every rand of this book's profit comes from the few tickets above it.
      </p>
    </Card>
  );
});
ExoticsTable.displayName = 'ExoticsTable';

function medianOf(values: number[]): number {
  if (values.length === 0) return 0;
  const s = [...values].sort((a, b) => a - b);
  const m = s.length >> 1;
  return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
}
