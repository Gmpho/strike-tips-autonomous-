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
export const TrackRoiChart: React.FC<{ roiByTrack: Record<string, number> | undefined }> = React.memo(
  ({ roiByTrack }) => {
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
      <Card title="ROI by Track">
        <ApexChart type="bar" series={series} options={options} height={Math.max(180, (series[0] as { data: unknown[] }).data.length * 44)} />
      </Card>
    );
  },
);
TrackRoiChart.displayName = 'TrackRoiChart';

// ── 4. ROI by odds bracket (columns) ─────────────────────────────
export const BracketChart: React.FC<{ bets: BetLike[] }> = React.memo(({ bets }) => {
  const { series, options, empty } = React.useMemo(() => {
    const settled = settledBets(bets);
    if (settled.length === 0) return { series: [], options: {}, empty: true as const };
    const m = bracketRoi(settled);
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
  }, [bets]);

  if (empty) return null;
  return (
    <Card title="ROI by Odds Bracket">
      <ApexChart type="bar" series={series} options={options} height={270} />
    </Card>
  );
});
BracketChart.displayName = 'BracketChart';

// ── 5. Win / loss donut ──────────────────────────────────────────
export const WinLossDonut: React.FC<{ wins: number; losses: number }> = React.memo(({ wins, losses }) => {
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
    <Card title="Win / Loss">
      <ApexChart type="donut" series={[wins, losses]} options={options} height={250} />
    </Card>
  );
});
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

// ── 7. Track × odds ROI heatmap ──────────────────────────────────
export const RoiHeatmap: React.FC<{ bets: BetLike[] }> = React.memo(({ bets }) => {
  const { series, options, empty } = React.useMemo(() => {
    const hm = roiHeatmap(settledBets(bets));
    if (hm.tracks.length === 0) return { series: [], options: {}, empty: true as const };
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
        formatter: (v: number | string) => (v === null || v === undefined || v === '' ? '–' : `${Number(v).toFixed(0)}%`),
        style: { fontSize: '11px', fontWeight: 800, colors: ['#f1f5f9'] },
      },
      xaxis: { categories: hm.brackets, axisTicks: { show: false } },
      tooltip: {
        ...apexBase.tooltip,
        y: { formatter: (v: number, o: never) => {
          const oo = o as unknown as { seriesIndex: number; dataPointIndex: number };
          const vol = hm.volumes[oo.seriesIndex]?.[oo.dataPointIndex] ?? 0;
          return `${Number(v).toFixed(1)}% ROI · ${vol} bets`;
        } },
      },
      legend: { show: false },
    };
    return {
      empty: false as const,
      options,
      series: hm.tracks.map((t, i) => ({
        name: t,
        data: hm.brackets.map((b, j) => ({ x: b, y: hm.matrix[i][j] })),
      })),
    };
  }, [bets]);

  if (empty) return null;
  return (
    <Card title="ROI Heatmap · Track × Odds" right={<span className="text-[10px] font-black text-theme-secondary">% ROI per cell</span>}>
      <ApexChart type="heatmap" series={series} options={options} height={260} />
    </Card>
  );
});
RoiHeatmap.displayName = 'RoiHeatmap';
