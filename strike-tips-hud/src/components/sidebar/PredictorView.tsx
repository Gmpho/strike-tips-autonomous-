import React from 'react';
import { Sparkles, Brain } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const PredictorView: React.FC = () => {
  const store = useHUD();
  const predictions = Array.isArray(store.predictions) ? store.predictions : [];

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6"
    >
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-purple-400 to-pink-500 bg-clip-text text-transparent">
          ATR Predictions
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          AI-powered race outcome predictions
        </p>
      </div>

      {predictions.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-theme-secondary">
          <Brain className="w-8 h-8 mb-3 opacity-50" />
          <p className="text-sm font-bold">No predictions available</p>
          <p className="text-xs opacity-70 mt-1">Data refreshes every 30s</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {predictions.map((pred, i) => (
            <motion.div
              key={`${pred.horse}-${i}`}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.03 }}
              className="p-5 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-purple-500/30 transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <h3 className="text-base font-black text-theme-primary group-hover:text-purple-400 transition-colors">
                  {pred.horse}
                </h3>
                <span className="px-2 py-0.5 rounded-full bg-purple-500/10 border border-purple-500/20 text-[9px] font-black text-purple-500 uppercase tracking-widest">
                  Tip
                </span>
              </div>
              <p className="text-sm text-theme-secondary font-bold leading-relaxed">
                {pred.prediction}
              </p>
            </motion.div>
          ))}
        </div>
      )}

      {predictions.length > 0 && (
        <div className="flex items-center gap-2 text-[10px] text-theme-secondary font-bold opacity-60">
          <Sparkles className="w-3 h-3" />
          {predictions.length} predictions loaded from ATR
        </div>
      )}
    </motion.div>
  );
};
