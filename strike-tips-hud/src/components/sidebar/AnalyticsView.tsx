import React from 'react';
import { TrendingUp, Activity, Target, BarChart2 } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const AnalyticsView: React.FC = () => {
  const { learning, betStats } = useHUD();
  
  const analytics = {
    winRate: betStats && betStats.totalBets > 0 ? (betStats.wins / betStats.totalBets * 100).toFixed(1) : '0.0',
    roi: betStats?.roi || learning?.totalRoi || 0,
    efficiency: 94, // Placeholder for now
    tracks: Object.entries(learning?.roiByTrack || {}).map(([name, roi]) => ({
      name: name.charAt(0).toUpperCase() + name.slice(1),
      roi: roi
    }))
  };

  // Fallback for visual completeness if no data yet
  const displayTracks = analytics.tracks.length > 0 ? analytics.tracks : [];
  
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-8"
    >
      {/* Header Section */}
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
          Intelligence Analytics
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Strategy Performance Metrics
        </p>
      </div>

      {/* KPI Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {[
          { label: 'WIN RATE', value: `${analytics.winRate}%`, icon: TrendingUp, color: 'text-emerald-500' },
          { label: 'TOTAL ROI', value: `${Number(analytics.roi).toFixed(1)}%`, icon: Target, color: 'text-blue-500' },
          { label: 'EFFICIENCY', value: `${analytics.efficiency}%`, icon: BarChart2, color: 'text-purple-500' },
        ].map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-theme-primary transition-colors">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className="text-xl font-black text-theme-primary mb-0.5 tabular">{stat.value}</div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Distribution by Track */}
      <div className="p-6 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
        <div className="flex items-center gap-3 mb-8">
          <Activity className="w-4 h-4 text-emerald-400" />
          <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">
            Distribution by Track
          </h3>
        </div>
        
        <div className="space-y-6">
          {displayTracks.map((track) => (
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
          Neural engine is prioritizing <span className="text-emerald-500">{learning?.topTrack || 'N/A'}</span> (+{learning?.accuracy || 0}% edge) based on recent volume variance. 
        </p>
      </div>
    </motion.div>
  );
};
