import React from 'react';
import { TrendingUp, Activity, Target, BarChart2, DollarSign, Layers } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

interface BankrollPoint {
  t: string;
  balance: number;
}

function InteractiveBankrollChart({ history }: { history: BankrollPoint[] }) {
  const [hoverIndex, setHoverIndex] = React.useState<number | null>(null);
  const [tooltipPos, setTooltipPos] = React.useState<{ x: number; y: number } | null>(null);
  const svgRef = React.useRef<SVGSVGElement>(null);

  if (history.length < 2) return null;

  const balances = history.map(h => h.balance);
  const min = Math.min(...balances);
  const max = Math.max(...balances);
  const range = max - min || 1;

  const w = 600;
  const h = 220;
  const paddingY = 24; // Prevents clipping at top and bottom

  const getX = (idx: number) => (idx / (history.length - 1)) * w;
  const getY = (val: number) => h - paddingY - ((val - min) / range) * (h - 2 * paddingY);

  const points = history.map((pt, idx) => `${getX(idx)},${getY(pt.balance)}`).join(' ');
  const areaPoints = `${getX(0)},${h} ${points} ${getX(history.length - 1)},${h}`;

  const isUp = balances[balances.length - 1] >= balances[0];
  const themeColor = isUp ? '#10b981' : '#ef4444';
  const gradientId = isUp ? 'green-gradient' : 'red-gradient';

  const handleMouseMove = (e: React.MouseEvent<SVGSVGElement>) => {
    if (!svgRef.current) return;
    const rect = svgRef.current.getBoundingClientRect();
    const mouseX = ((e.clientX - rect.left) / rect.width) * w;
    
    let closestIdx = 0;
    let minDiff = Infinity;
    
    for (let i = 0; i < history.length; i++) {
      const x = getX(i);
      const diff = Math.abs(x - mouseX);
      if (diff < minDiff) {
        minDiff = diff;
        closestIdx = i;
      }
    }
    
    setHoverIndex(closestIdx);
    
    const xPct = (getX(closestIdx) / w) * rect.width;
    const yPct = (getY(history[closestIdx].balance) / h) * rect.height;
    
    setTooltipPos({ x: xPct, y: yPct });
  };

  const handleMouseLeave = () => {
    setHoverIndex(null);
    setTooltipPos(null);
  };

  const gridLinesY = [min, min + range * 0.33, min + range * 0.66, max];

  return (
    <div className="relative w-full">
      {/* Absolute positioned y-axis labels to prevent SVG text scaling blur */}
      <div className="absolute left-0 top-0 bottom-0 flex flex-col justify-between text-[9px] font-black text-theme-secondary/40 select-none pointer-events-none z-10 py-5">
        <span>R{max.toFixed(0)}</span>
        <span>R{(min + range * 0.66).toFixed(0)}</span>
        <span>R{(min + range * 0.33).toFixed(0)}</span>
        <span>R{min.toFixed(0)}</span>
      </div>

      <div className="pl-14 pr-2">
        <svg
          ref={svgRef}
          viewBox={`0 0 ${w} ${h}`}
          className="w-full h-44 overflow-visible cursor-crosshair relative"
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <linearGradient id="green-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#10b981" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#10b981" stopOpacity="0.0" />
            </linearGradient>
            <linearGradient id="red-gradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.25" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.0" />
            </linearGradient>

            <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Dotted horizontal gridlines */}
          {gridLinesY.map((val, idx) => (
            <line
              key={idx}
              x1="0"
              y1={getY(val)}
              x2={w}
              y2={getY(val)}
              stroke="currentColor"
              className="text-theme-secondary/10"
              strokeWidth="1"
              strokeDasharray="4 6"
            />
          ))}

          {/* Glowing main path shadow */}
          <path
            d={`M ${points}`}
            fill="none"
            stroke={themeColor}
            strokeWidth="6"
            strokeLinecap="round"
            className="opacity-20 blur-md pointer-events-none"
          />

          {/* Gradient area fill */}
          <path
            d={`M ${areaPoints}`}
            fill={`url(#${gradientId})`}
            className="pointer-events-none"
          />

          {/* Main trendline */}
          <path
            d={`M ${points}`}
            fill="none"
            stroke={themeColor}
            strokeWidth="3.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="pointer-events-none"
          />

          {/* Interactive tracking elements */}
          {hoverIndex !== null && (
            <>
              <line
                x1={getX(hoverIndex)}
                y1="0"
                x2={getX(hoverIndex)}
                y2={h}
                stroke="currentColor"
                className="text-purple-500/30"
                strokeWidth="1.5"
                strokeDasharray="3 3"
                pointerEvents="none"
              />

              <circle
                cx={getX(hoverIndex)}
                cy={getY(history[hoverIndex].balance)}
                r="7"
                fill={themeColor}
                className="opacity-30 animate-ping"
                pointerEvents="none"
              />
              <circle
                cx={getX(hoverIndex)}
                cy={getY(history[hoverIndex].balance)}
                r="4.5"
                fill={themeColor}
                stroke="#1e1b4b"
                strokeWidth="2"
                pointerEvents="none"
              />
            </>
          )}
        </svg>
      </div>

      {/* Glassmorphic floating tooltip */}
      <AnimatePresence>
        {hoverIndex !== null && tooltipPos && (
          <motion.div
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 10, scale: 0.95 }}
            transition={{ duration: 0.15 }}
            className="absolute z-50 bg-theme-panel/95 backdrop-blur-2xl border border-purple-500/30 p-3 rounded-xl shadow-2xl pointer-events-none text-left"
            style={{
              left: `${tooltipPos.x + 36}px`,
              top: `${tooltipPos.y - 64}px`,
            }}
          >
            <div className="text-[8px] font-black text-theme-secondary uppercase tracking-widest mb-0.5">
              {new Date(history[hoverIndex].t).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
            </div>
            <div className="text-sm font-black text-theme-primary tabular-nums">
              R {history[hoverIndex].balance.toLocaleString([], { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const AnalyticsView: React.FC = () => {
  const { learning, betStats, bankroll, bankrollHistory } = useHUD();
  const [hoveredBracket, setHoveredBracket] = React.useState<string | null>(null);

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

      {/* Bankroll History Chart */}
      {chartBalances.length >= 2 && (
        <div className="p-6 rounded-2xl bg-theme-panel border border-theme">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <TrendingUp className={`w-4 h-4 ${chartTrend ? 'text-emerald-400' : 'text-red-400'}`} />
              <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">Bankroll History</h3>
            </div>
            <span className={`text-xs font-black tabular ${chartTrend ? 'text-emerald-400' : 'text-red-400'}`}>
              R{chartBalances[0].toFixed(0)} → R{chartBalances[chartBalances.length - 1].toFixed(0)}
            </span>
          </div>
          <InteractiveBankrollChart history={bankrollHistory} />
          <div className="flex justify-between text-[9px] text-theme-secondary font-black mt-2 pl-14 pr-2">
            <span>{bankrollHistory[0]?.t}</span>
            <span>{bankrollHistory[bankrollHistory.length - 1]?.t}</span>
          </div>
        </div>
      )}

      {/* Best / Worst Track */}
      {(bestTrack || worstTrack) && (
        <div className="grid grid-cols-2 gap-4">
          {bestTrack && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-emerald-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Best Track</div>
              <div className="text-theme-primary font-black">{bestTrack.name}</div>
              <div className="text-emerald-400 font-black tabular">+{bestTrack.roi}% ROI</div>
            </div>
          )}
          {worstTrack && worstTrack.name !== bestTrack?.name && (
            <div className="p-4 rounded-2xl bg-theme-panel border border-red-500/20">
              <div className="text-[10px] text-theme-secondary font-black uppercase tracking-widest mb-1">Worst Track</div>
              <div className="text-theme-primary font-black">{worstTrack.name}</div>
              <div className="text-red-400 font-black tabular">{worstTrack.roi}% ROI</div>
            </div>
          )}
        </div>
      )}

      {/* ROI by Odds Range Bar Chart */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme">
        <div className="flex items-center gap-3 mb-6">
          <BarChart2 className="w-4 h-4 text-purple-400" />
          <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">
            ROI by Odds Bracket
          </h3>
        </div>
        
        {(() => {
          const raw = learning?.roiByOddsRange;
          if (!raw) return <p className="text-xs text-theme-secondary font-bold">No settled odds bracket data yet.</p>;
          
          const brackets = ['odds_under_2', 'odds_2_to_4', 'odds_4_to_7', 'odds_7_plus'];
          let normalized: Record<string, any> = {};

          if (Array.isArray(raw)) {
            raw.forEach((item: any) => {
              const bKey = item.bracket || 'odds_2_to_4';
              normalized[bKey] = item;
            });
          } else if (typeof raw === 'object') {
            normalized = raw;
          }

          const hasData = brackets.some(k => normalized[k] && (normalized[k].total > 0 || normalized[k].total_bets > 0));
          if (!hasData && Object.keys(normalized).length === 0) {
            return <p className="text-xs text-theme-secondary font-bold">No settled odds bracket data yet.</p>;
          }

          return (
            <div className="grid grid-cols-4 gap-4 h-36 items-end pt-4">
              {brackets.map((key) => {
                const data = normalized[key] || {};
                const label = key === 'odds_under_2' ? '< 2.0' : key === 'odds_2_to_4' ? '2.0 - 4.0' : key === 'odds_4_to_7' ? '4.0 - 7.0' : '7.0+';
                const roiVal = Number(data.roi ?? 0);
                const wins = Number(data.wins ?? 0);
                const total = Number(data.total ?? data.total_bets ?? 0);
                const staked = Number(data.staked ?? data.total_stake ?? 0);
                const returned = Number(data.returned ?? data.total_returned ?? (staked + (data.profit_loss || 0)));
                const wr = total > 0 ? ((wins / total) * 100).toFixed(0) : '0';
                // Map -50% to +100% to height percentage (min 10%, max 100%)
                const heightPct = Math.max(10, Math.min(100, ((roiVal + 50) / 150) * 100));
                
                return (
                  <div
                    key={key}
                    className="flex flex-col items-center h-full justify-end group relative"
                    onMouseEnter={() => setHoveredBracket(key)}
                    onMouseLeave={() => setHoveredBracket(null)}
                  >
                    {/* Floating stats tooltip on hover */}
                    <AnimatePresence>
                      {hoveredBracket === key && (
                        <motion.div
                          initial={{ opacity: 0, y: -5, scale: 0.95 }}
                          animate={{ opacity: 1, y: 0, scale: 1 }}
                          exit={{ opacity: 0, y: -5, scale: 0.95 }}
                          transition={{ duration: 0.15 }}
                          className="absolute z-30 bottom-full mb-3 bg-theme-panel/95 backdrop-blur-xl border border-purple-500/30 p-3 rounded-xl shadow-2xl text-[10px] font-black text-theme-primary text-center w-28 pointer-events-none"
                        >
                          <div className="text-purple-400 uppercase tracking-widest text-[8px] mb-1">Stats</div>
                          <div className="text-theme-secondary">WR: <span className="text-theme-primary">{wr}%</span></div>
                          <div className="text-theme-secondary">Vol: <span className="text-theme-primary">{total} bets</span></div>
                          <div className="text-theme-secondary mt-1 border-t border-theme/50 pt-1">
                            Net: <span className={roiVal >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                              R{(returned - staked).toFixed(0)}
                            </span>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    <span className={`text-[10px] font-black tabular mb-2 transition-opacity ${roiVal >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {roiVal >= 0 ? '+' : ''}{roiVal.toFixed(0)}%
                    </span>
                    
                    {/* Cylinder Column Glass Container */}
                    <div className="w-10 bg-black/35 rounded-t-full relative overflow-hidden border border-white/5 flex items-end h-full max-h-[110px] shadow-inner">
                      <motion.div
                        initial={{ height: 0 }}
                        animate={{ height: `${heightPct}%` }}
                        transition={{ duration: 0.8, ease: "easeOut" }}
                        className={`w-full rounded-t-full relative ${
                          roiVal >= 0
                            ? 'bg-gradient-to-t from-emerald-600/80 to-emerald-400 shadow-[0_0_12px_rgba(16,185,129,0.3)]'
                            : 'bg-gradient-to-t from-red-600/80 to-red-400 shadow-[0_0_12px_rgba(239,68,68,0.3)]'
                        }`}
                        style={{ height: `${heightPct}%` }}
                      >
                        {/* Vertical highlight glass refraction line */}
                        <div className="absolute inset-y-0 left-1 w-1 bg-white/20 rounded-full blur-[0.5px]" />
                      </motion.div>
                    </div>
                    
                    <span className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase mt-2 text-center whitespace-nowrap">
                      {label}
                    </span>
                  </div>
                );
              })}
            </div>
          );
        })()}
      </div>

      {/* Distribution by Track */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme">
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
