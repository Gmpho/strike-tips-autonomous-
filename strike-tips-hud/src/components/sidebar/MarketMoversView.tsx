import React from 'react';
import { TrendingUp, TrendingDown, Minus, Eye } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

function MovementIcon({ movement }: { movement: string }) {
  const m = movement?.toLowerCase() || '';
  if (m.includes('down') || m.startsWith('-')) {
    return <TrendingDown className="w-4 h-4 text-emerald-500" />;
  }
  if (m.includes('up') || m.startsWith('+')) {
    return <TrendingUp className="w-4 h-4 text-red-500" />;
  }
  return <Minus className="w-4 h-4 text-theme-secondary" />;
}

function MovementColor({ movement }: { movement: string }) {
  const m = movement?.toLowerCase() || '';
  if (m.includes('down') || m.startsWith('-')) return 'text-emerald-500';
  if (m.includes('up') || m.startsWith('+')) return 'text-red-500';
  return 'text-theme-secondary';
}

export const MarketMoversView: React.FC = () => {
  const store = useHUD();
  const marketMovers = Array.isArray(store.marketMovers) ? store.marketMovers : [];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6"
    >
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-amber-400 to-orange-500 bg-clip-text text-transparent">
          Market Movers
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Horses with significant odds movement
        </p>
      </div>

      {marketMovers.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-theme-secondary">
          <Eye className="w-8 h-8 mb-3 opacity-50" />
          <p className="text-sm font-bold">No market movers yet</p>
          <p className="text-xs opacity-70 mt-1">Data refreshes every 30s</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-theme">
                <th className="text-left py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">Horse</th>
                <th className="text-left py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">Course</th>
                <th className="text-left py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">Time</th>
                <th className="text-right py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">Current</th>
                <th className="text-right py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">1st Show</th>
                <th className="text-right py-3 px-4 text-[10px] font-black text-theme-secondary uppercase tracking-widest">Movement</th>
              </tr>
            </thead>
            <tbody>
              {marketMovers.map((mover, i) => (
                <motion.tr
                  key={`${mover.horse}-${mover.course}-${i}`}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.02 }}
                  className="border-b border-theme/50 last:border-0 hover:bg-theme-secondary/30 transition-colors"
                >
                  <td className="py-3 px-4 font-bold text-theme-primary">{mover.horse}</td>
                  <td className="py-3 px-4 text-theme-secondary font-bold uppercase tracking-tight">{mover.course}</td>
                  <td className="py-3 px-4 text-theme-secondary font-bold tabular">{mover.time}</td>
                  <td className="py-3 px-4 text-right font-bold tabular text-theme-primary">{mover.current_odds}</td>
                  <td className="py-3 px-4 text-right font-bold tabular text-theme-secondary">{mover.first_show}</td>
                  <td className="py-3 px-4 text-right">
                    <span className={`inline-flex items-center gap-1.5 font-bold tabular ${MovementColor({ movement: mover.movement })}`}>
                      <MovementIcon movement={mover.movement} />
                      {mover.movement}
                    </span>
                  </td>
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {marketMovers.length > 0 && (
        <p className="text-[10px] text-theme-secondary font-bold opacity-60">
          {marketMovers.length} movers tracked — updated live from ATR
        </p>
      )}
    </motion.div>
  );
};
