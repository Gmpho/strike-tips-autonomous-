import React, { Suspense } from 'react';
import { TrendingUp, Activity, Target, BarChart2, DollarSign, Layers } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import {
  settledBets,
  scopedBets,
  singlesOnly,
  trackRoi,
  type BetLike,
} from '../../lib/analytics';

// ApexCharts suite ships in its own on-demand chunk (treeshaken core +
// 7 types) so the dashboard first paint never pays for it. Loaded inside
// ApexSuite below via dynamic import.

function ChartSkeleton() {
  return (
    <div className="p-6 rounded-2xl bg-theme-panel border border-theme animate-pulse">
      <div className="h-3 w-40 rounded bg-white/10 mb-4" />
      <div className="h-56 rounded-xl bg-white/5" />
    </div>
  );
}

export const AnalyticsView: React.FC = () => {
  const { learning, bankroll, bankrollHistory, betHistory } = useHUD();

  // Single universe (Oct-2026): every number on this page derives from the
  // SAME scoped settled set. Previously KPIs mixed paper+real, the equity
  // curve was paper-only, and odds cells were detonated by exotic dividends.
  const paperMode = (bankroll as unknown as { paperMode?: boolean })?.paperMode;
  const scoped = React.useMemo(
    () => scopedBets((betHistory || []) as BetLike[], paperMode),
    [betHistory, paperMode],
  );
  const settled = React.useMemo(() => settledBets(scoped), [scoped]);
  const singles = React.useMemo(() => settledBets(singlesOnly(scoped)), [scoped]);

  const wins = settled.filter((b) => b.won).length;
  const losses = settled.length - wins;
  const stakeTotal = settled.reduce((s, b) => s + b.stake, 0);
  const payoutTotal = settled.reduce((s, b) => s + b.payout, 0);

  const winRate = settled.length > 0 ? ((wins / settled.length) * 100).toFixed(1) : '0.0';
  const roi = stakeTotal > 0 ? (((payoutTotal - stakeTotal) / stakeTotal) * 100) : 0;

  // Real efficiency: payout / staked (return efficiency %)
  const efficiency = stakeTotal > 0 ? ((payoutTotal / stakeTotal) * 100).toFixed(1) : '0.0';

  const avgStake = settled.length > 0 ? (stakeTotal / settled.length).toFixed(2) : '0.00';
  const totalPL = (payoutTotal - stakeTotal).toFixed(2);

  const openBetsValue = bankroll?.totalExposure?.toFixed(2) ?? '0.00';

  const tracks = React.useMemo(() => trackRoi(settled), [settled]);

  const bestTrack = tracks.length > 0 && tracks[tracks.length - 1].roi > 0
    ? tracks[tracks.length - 1] : null;
  const worstTrack = tracks.length > 0 && tracks[0].roi < 0 ? tracks[0] : null;

  const kpis = [
    { label: 'WIN RATE', value: `${winRate}%`, icon: TrendingUp, color: 'text-emerald-500' },
    { label: 'TOTAL ROI', value: `${Number(roi).toFixed(1)}%`, icon: Target, color: 'text-blue-500' },
    { label: 'EFFICIENCY', value: `${efficiency}%`, icon: BarChart2, color: 'text-purple-500' },
    { label: 'AVG STAKE', value: `R${avgStake}`, icon: Layers, color: 'text-amber-500' },
    { label: 'TOTAL P&L', value: `R${totalPL}`, icon: DollarSign, color: Number(totalPL) >= 0 ? 'text-emerald-500' : 'text-red-500' },
    { label: 'OPEN EXPOSURE', value: `R${openBetsValue}`, icon: Activity, color: 'text-cyan-500' },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-3.5 sm:p-6 space-y-5 sm:space-y-8 w-full"
    >
      <div>
        <h2 className="text-xl sm:text-2xl font-bold bg-linear-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          Intelligence Analytics
        </h2>
        <p className="text-[10px] sm:text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Strategy Performance Metrics
        </p>
      </div>

      {/* KPI Grid — 6 cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-3 sm:gap-4">
        {kpis.map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme group hover:border-theme-primary transition-colors">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className="text-xl font-black text-theme-primary mb-0.5 tabular">{stat.value}</div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* ApexCharts suite (lazy chunk) */}
      <Suspense fallback={<><ChartSkeleton /><ChartSkeleton /></>}>
        <ApexSuite
          bankrollHistory={bankrollHistory}
          bets={scoped}
          singles={singles}
          wins={wins}
          losses={losses}
          trackRows={tracks}
        />
      </Suspense>

      {/* Best / Worst Track */}
      {(bestTrack || worstTrack) && (
        <div className={`grid ${bestTrack && worstTrack ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
          {bestTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-emerald-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Best Track</div>
              <div className="text-theme-primary font-black">{bestTrack.name}</div>
              <div className="text-emerald-400 font-black tabular">+{bestTrack.roi.toFixed(1)}% ROI</div>
            </div>
          )}
          {worstTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-red-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Worst Track</div>
              <div className="text-theme-primary font-black">{worstTrack.name}</div>
              <div className="text-red-400 font-black tabular">{worstTrack.roi.toFixed(1)}% ROI</div>
            </div>
          )}
        </div>
      )}

      {/* Learning Insights */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme group hover:border-emerald-500/30 transition-all duration-500">
        <div className="flex items-center gap-3 mb-4">
          <Target className="w-4 h-4 text-blue-500" />
          <h3 className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
            Learning Engine Insights
          </h3>
        </div>
        <p className="text-sm text-theme-secondary leading-relaxed font-bold group-hover:text-theme-primary transition-colors">
          Neural engine is prioritizing{' '}
          <span className="text-emerald-500">{learning?.topTrack || 'N/A'}</span>
          {' '}({learning?.accuracy !== undefined && learning.accuracy !== 0
            ? `${learning.accuracy > 0 ? '+' : ''}${learning.accuracy}% vs implied`
            : 'awaiting data'
          }) based on recent volume variance.
        </p>
      </div>
    </motion.div>
  );
};

// Separate component so the lazy chunk boundary is explicit and the charts
// mount only after the KPI paint.
const ApexSuite: React.FC<{
  bankrollHistory: { t: string; balance: number }[];
  bets: BetLike[];
  singles: BetLike[];
  wins: number;
  losses: number;
  trackRows: { name: string; roi: number }[];
}> = ({ bankrollHistory, bets, singles, wins, losses, trackRows }) => {
  const [Charts, setCharts] = React.useState<typeof import('../analytics/AnalyticsCharts') | null>(null);

  React.useEffect(() => {
    let live = true;
    import('../analytics/AnalyticsCharts').then((m) => {
      if (live) setCharts(m);
    });
    return () => {
      live = false;
    };
  }, []);

  // Touch-free dynamic chunk: bundlers split on import().
  if (!Charts) return <><ChartSkeleton /><ChartSkeleton /></>;
  return (
    <div className="space-y-5 sm:space-y-8">
      <Charts.EquityChart history={bankrollHistory} />
      <Charts.DailyPnlChart bets={bets} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.TrackRoiChart rows={trackRows} />
        <Charts.WinLossDonut wins={wins} losses={losses} />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.BracketChart bets={singles} />
        <Charts.PnlHistogram bets={bets} />
      </div>
      <Charts.RoiHeatmap bets={singles} />
    </div>
  );
};
