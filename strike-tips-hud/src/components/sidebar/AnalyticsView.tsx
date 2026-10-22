import React, { Suspense } from 'react';
import { TrendingUp, Activity, Target, BarChart2, DollarSign, Layers } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

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
  const { learning, betStats, bankroll, bankrollHistory, betHistory } = useHUD();

  // Win rate + avg stake over SETTLED bets only — totalBets includes the
  // refund backlog, which once collapsed the rate to single digits.
  const settledCount = betStats?.settledBets
    ?? ((betStats?.wins ?? 0) + (betStats?.losses ?? 0));

  const winRate = settledCount > 0
    ? ((betStats?.wins ?? 0) / settledCount * 100).toFixed(1)
    : '0.0';

  const roi = betStats?.roi ?? learning?.totalRoi ?? 0;

  // Profit factor: gross returns / lost stakes. Reported as "—" until at
  // least one settled ticket has lost (division by zero is not a 316% edge).
  const profitFactor = betStats?.profitFactor != null
    ? `${Number(betStats.profitFactor).toFixed(2)}×`
    : '—';

  const avgStake = betStats
    ? (betStats.avgStake ?? (settledCount > 0 ? betStats.stakeTotal / settledCount : 0)).toFixed(2)
    : '0.00';

  const totalPL = betStats
    ? (betStats.payoutTotal - betStats.stakeTotal).toFixed(2)
    : '0.00';

  const openBetsValue = bankroll?.totalExposure?.toFixed(2) ?? '0.00';

  // Coverage disclosure: 1,051 expired tickets are refunds, not losses, so
  // ROI is measured on a settled subset. Show the subset size, not a fake ROI.
  const coverage = betStats?.settlementRate != null
    ? `${betStats.settlementRate.toFixed(0)}%`
    : null;
  const expiredCount = betStats?.expiredBets ?? 0;

  const allTracks = Object.entries(learning?.roiByTrack || {}).map(([name, r]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    roi: Number(r) || 0
  }));

  const nonZeroTracks = allTracks.filter(t => t.roi !== 0);
  const tracks = (nonZeroTracks.length > 0 ? nonZeroTracks : allTracks.slice(0, 7)).sort((a, b) => b.roi - a.roi);

  // Rankings come from the ledger with a min-sample + 90-day recency gate
  // (kenilworth's +351% was 11 settled winners out of 105 tickets, last run
  // in August). Fall back to the chart series only if the server omits them.
  const bestTrack = learning?.bestTrack
    ? { name: learning.bestTrack.name, roi: learning.bestTrack.roi, n: learning.bestTrack.n, lastSeen: learning.bestTrack.lastSeen }
    : tracks.length > 0 && tracks[0].roi > 0
      ? { name: tracks[0].name, roi: tracks[0].roi, n: null as number | null, lastSeen: null as string | null }
      : null;
  const worstTrack = learning?.worstTrack && learning.worstTrack.roi < 0
    ? { name: learning.worstTrack.name, roi: learning.worstTrack.roi, n: learning.worstTrack.n, lastSeen: learning.worstTrack.lastSeen }
    : tracks.length > 0 && tracks[tracks.length - 1].roi < 0
      ? { name: tracks[tracks.length - 1].name, roi: tracks[tracks.length - 1].roi, n: null as number | null, lastSeen: null as string | null }
      : null;

  const lastRun = (value: string | null) => value
    ? new Date(`${value}T12:00:00`).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short' })
    : null;

  const kpis: { label: string; value: string; icon: typeof TrendingUp; color: string; sub?: string }[] = [
    { label: 'WIN RATE', value: `${winRate}%`, icon: TrendingUp, color: 'text-emerald-500', sub: `${settledCount} settled` },
    { label: 'TOTAL ROI', value: `${Number(roi).toFixed(1)}%`, icon: Target, color: 'text-blue-500', sub: coverage ? `${coverage} coverage · ${expiredCount} expired` : undefined },
    { label: 'PROFIT FACTOR', value: profitFactor, icon: BarChart2, color: 'text-purple-500', sub: 'returns ÷ lost stakes' },
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
            {stat.sub && (
              <div className="text-[9px] text-theme-secondary/70 font-bold mt-1 normal-case">{stat.sub}</div>
            )}
          </div>
        ))}
      </div>

      {/* ApexCharts suite (lazy chunk) */}
      <Suspense fallback={<><ChartSkeleton /><ChartSkeleton /></>}>
        <ApexSuite
          bankrollHistory={bankrollHistory}
          betHistory={betHistory}
          betStats={betStats}
          roiByTrack={learning?.roiByTrack}
        />
      </Suspense>

      {/* Best / Worst Track */}
      {(bestTrack || worstTrack) && (
        <div className={`grid ${bestTrack && worstTrack ? 'grid-cols-2' : 'grid-cols-1'} gap-4`}>
          {bestTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-emerald-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Best Track</div>
              <div className="text-theme-primary font-black">{bestTrack.name}</div>
              <div className="text-emerald-400 font-black tabular">{bestTrack.roi >= 0 ? '+' : ''}{bestTrack.roi.toFixed(1)}% ROI</div>
              <div className="text-[9px] text-theme-secondary/70 font-bold mt-1">
                {bestTrack.n != null ? `${bestTrack.n} settled` : 'settled sample'}
                {lastRun(bestTrack.lastSeen) ? ` · last ${lastRun(bestTrack.lastSeen)}` : ''}
              </div>
            </div>
          )}
          {worstTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-red-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Worst Track</div>
              <div className="text-theme-primary font-black">{worstTrack.name}</div>
              <div className="text-red-400 font-black tabular">{worstTrack.roi.toFixed(1)}% ROI</div>
              <div className="text-[9px] text-theme-secondary/70 font-bold mt-1">
                {worstTrack.n != null ? `${worstTrack.n} settled` : 'settled sample'}
                {lastRun(worstTrack.lastSeen) ? ` · last ${lastRun(worstTrack.lastSeen)}` : ''}
              </div>
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
        <div className="space-y-2 text-sm text-theme-secondary leading-relaxed font-bold group-hover:text-theme-primary transition-colors">
          <p>
            Best settled track:{' '}
            <span className="text-emerald-500">{bestTrack?.name ?? 'N/A'}</span>
            {bestTrack ? ` (${bestTrack.roi >= 0 ? '+' : ''}${bestTrack.roi.toFixed(1)}%, ` : ' ('}
            <span className="text-theme-primary">
              {bestTrack?.n ?? 0} settled{lastRun(bestTrack?.lastSeen ?? null) ? ` · last ${lastRun(bestTrack?.lastSeen ?? null)}` : ''}
            </span>
            {`), minimum ${learning?.minSample ?? 20} settled and ${learning?.recencyDays ?? 90}-day window.`}
          </p>
          <p>
            Book calibration:{' '}
            <span className={Number(learning?.accuracy) >= 0 ? 'text-emerald-500' : 'text-red-400'}>
              {Number(learning?.accuracy ?? 0) > 0 ? '+' : ''}{Number(learning?.accuracy ?? 0).toFixed(1)}%
            </span>
            {' vs implied, across '}
            <span className="text-theme-primary">{settledCount}</span>
            {' settled tickets.'}
            {betStats?.roiIncludingExpired != null && expiredCount > 0 && (
              <span className="text-theme-secondary/70"> If expired tickets were counted as losses, ROI would read {Number(betStats.roiIncludingExpired).toFixed(1)}%.</span>
            )}
          </p>
        </div>
      </div>
    </motion.div>
  );
};

// Separate component so the lazy chunk boundary is explicit and the charts
// mount only after the KPI paint.
const ApexSuite: React.FC<{
  bankrollHistory: { t: string; balance: number }[];
  betHistory: never[] | unknown[];
  betStats: { wins: number; losses: number } | undefined | null;
  roiByTrack: Record<string, number> | undefined;
}> = ({ bankrollHistory, betHistory, betStats, roiByTrack }) => {
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
  const bets = (betHistory || []) as never[];
  return (
    <div className="space-y-5 sm:space-y-8">
      <Charts.EquityChart history={bankrollHistory} />
      <Charts.DailyPnlChart bets={bets} />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.TrackRoiChart roiByTrack={roiByTrack} />
        <Charts.WinLossDonut wins={betStats?.wins ?? 0} losses={betStats?.losses ?? 0} />
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-5 sm:gap-8">
        <Charts.BracketChart bets={bets} />
        <Charts.PnlHistogram bets={bets} />
      </div>
      <Charts.RoiHeatmap bets={bets} />
    </div>
  );
};
