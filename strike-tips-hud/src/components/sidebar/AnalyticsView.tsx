import React from 'react';
import { TrendingUp, Activity, Target, BarChart2, DollarSign, Layers } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

// Minimal SVG sparkline — no extra deps needed
function Sparkline({ data, color = '#10b981' }: { data: number[]; color?: string }) {
  if (data.length < 2) return null;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;
  const w = 200, h = 48;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h;
    return `${x},${y}`;
  }).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-12" preserveAspectRatio="none">
      <polyline points={pts} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  );
}

export const AnalyticsView: React.FC = () => {
  const { learning, betStats, bankroll, bankrollHistory } = useHUD();

  const winRate = betStats && betStats.totalBets > 0
    ? (betStats.wins / betStats.totalBets * 100).toFixed(1)
    : '0.0';

  const roi = betStats?.roi ?? learning?.totalRoi ?? 0;

  // Real efficiency: payout / staked (return efficiency %)
  const efficiency = betStats && betStats.stakeTotal > 0
    ? ((betStats.payoutTotal / betStats.stakeTotal) * 100).toFixed(1)
    : '0.0';

  const avgStake = betStats && betStats.totalBets > 0
    ? (betStats.stakeTotal / betStats.totalBets).toFixed(2)
    : '0.00';

  const totalPL = betStats
    ? (betStats.payoutTotal - betStats.stakeTotal).toFixed(2)
    : '0.00';

  const openBetsValue = bankroll?.totalExposure?.toFixed(2) ?? '0.00';

  const tracks = Object.entries(learning?.roiByTrack || {}).map(([name, roi]) => ({
    name: name.charAt(0).toUpperCase() + name.slice(1),
    roi: roi as number
  }));

  const sortedTracks = [...tracks].sort((a, b) => b.roi - a.roi);
  const bestTrack = sortedTracks[0];
  const worstTrack = sortedTracks[sortedTracks.length - 1];

  const chartBalances = bankrollHistory.map(p => p.balance);
  const chartTrend = chartBalances.length >= 2
    ? chartBalances[chartBalances.length - 1] >= chartBalances[0]
    : true;

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
      className="p-6 space-y-8"
    >
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          Intelligence Analytics
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Strategy Performance Metrics
        </p>
      </div>

      {/* KPI Grid — 6 cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {kpis.map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-theme-primary transition-colors">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className="text-xl font-black text-theme-primary mb-0.5 tabular">{stat.value}</div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Bankroll History Chart */}
      {chartBalances.length >= 2 && (
        <div className="p-6 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <TrendingUp className={`w-4 h-4 ${chartTrend ? 'text-emerald-400' : 'text-red-400'}`} />
              <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">Bankroll History</h3>
            </div>
            <span className={`text-xs font-black tabular ${chartTrend ? 'text-emerald-400' : 'text-red-400'}`}>
              R{chartBalances[0].toFixed(0)} → R{chartBalances[chartBalances.length - 1].toFixed(0)}
            </span>
          </div>
          <Sparkline data={chartBalances} color={chartTrend ? '#10b981' : '#ef4444'} />
          <div className="flex justify-between text-[10px] text-theme-secondary font-black mt-1">
            <span>{bankrollHistory[0]?.t}</span>
            <span>{bankrollHistory[bankrollHistory.length - 1]?.t}</span>
          </div>
        </div>
      )}

      {/* Best / Worst Track */}
      {(bestTrack || worstTrack) && (
        <div className="grid grid-cols-2 gap-4">
          {bestTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-emerald-500/20 backdrop-blur-xl">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Best Track</div>
              <div className="text-theme-primary font-black">{bestTrack.name}</div>
              <div className="text-emerald-400 font-black tabular">+{bestTrack.roi}% ROI</div>
            </div>
          )}
          {worstTrack && worstTrack.name !== bestTrack?.name && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-red-500/20 backdrop-blur-xl">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Worst Track</div>
              <div className="text-theme-primary font-black">{worstTrack.name}</div>
              <div className="text-red-400 font-black tabular">{worstTrack.roi}% ROI</div>
            </div>
          )}
        </div>
      )}

      {/* Distribution by Track */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-8">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">
            ROI by Track
          </h3>
        </div>
        {tracks.length === 0 ? (
          <p className="text-xs text-theme-secondary font-bold">No settled bets yet — ROI will populate after results are recorded.</p>
        ) : (
          <div className="space-y-6">
            {tracks.map((track) => (
              <div key={track.name} className="space-y-2">
                <div className="flex justify-between text-xs">
                  <span className="text-theme-primary font-black uppercase tracking-tight">{track.name}</span>
                  <span className={`font-black tabular ${track.roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {track.roi >= 0 ? '+' : ''}{track.roi}% ROI
                  </span>
                </div>
                <div className="h-1.5 w-full bg-theme-secondary rounded-full overflow-hidden border border-theme/50">
                  <motion.div
                    initial={{ width: 0 }}
                    animate={{ width: `${Math.max(5, Math.min(100, 50 + (track.roi * 2)))}%` }}
                    transition={{ duration: 1, ease: "easeOut" }}
                    className={`h-full rounded-full ${track.roi >= 0 ? 'bg-emerald-500' : 'bg-red-500'} shadow-[0_0_8px_rgba(16,185,129,0.2)]`}
                  />
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Learning Insights */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-emerald-500/30 transition-all duration-500">
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
