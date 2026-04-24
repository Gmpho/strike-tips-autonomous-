import React from 'react';
import { BarChart3, TrendingUp, Activity, Target } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const AnalyticsView: React.FC = () => {
  const state = useHUD();
  const roi = state.learning?.totalRoi || 0;
  const balance = state.bankroll?.balance || 0;
  const startingBalance = 2500; // Mock starting balance for analytics
  const profit = balance - startingBalance;
  
  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-8 h-full flex flex-col"
    >
      <div className="flex items-center justify-between mb-8 max-w-5xl mx-auto w-full">
        <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
          <BarChart3 className="w-6 h-6 text-emerald-500" />
          Intelligence Analytics
        </h2>
      </div>

      <div className="grid gap-6 max-w-5xl mx-auto w-full">
        {/* Top KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <motion.div 
            whileHover={{ y: -5, scale: 1.02 }}
            className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <TrendingUp className="w-5 h-5 text-emerald-400" />
              <span className="text-xs font-black uppercase tracking-wider">Total Return on Investment</span>
            </div>
            <div className={`text-4xl font-black ${roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              {roi >= 0 ? '+' : ''}{roi.toFixed(2)}%
            </div>
          </motion.div>

          <motion.div 
            whileHover={{ y: -5, scale: 1.02 }}
            className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Activity className="w-5 h-5 text-blue-400" />
              <span className="text-xs font-black uppercase tracking-wider">Net Profit / Loss</span>
            </div>
            <div className={`text-4xl font-black ${profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
              R {Math.abs(profit).toFixed(2)}
            </div>
          </motion.div>

          <motion.div 
            whileHover={{ y: -5, scale: 1.02 }}
            className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
          >
            <div className="flex items-center gap-2 text-slate-500 mb-2">
              <Target className="w-5 h-5 text-purple-400" />
              <span className="text-xs font-black uppercase tracking-wider">Strike Rate</span>
            </div>
            <div className="text-4xl font-black text-white">
              64.2%
            </div>
          </motion.div>
        </div>

        {/* Chart Placeholder Area */}
        <motion.div 
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-8 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] min-h-[400px] flex flex-col items-center justify-center relative overflow-hidden"
        >
          {/* Decorative Grid Background */}
          <div className="absolute inset-0 bg-[linear-gradient(to_right,#80808012_1px,transparent_1px),linear-gradient(to_bottom,#80808012_1px,transparent_1px)] bg-size-[24px_24px]"></div>
          
          <div className="relative z-10 flex flex-col items-center text-center">
            <BarChart3 className="w-16 h-16 text-white/10 mb-4" />
            <h3 className="text-xl font-bold text-white mb-2">Data Aggregation in Progress</h3>
            <p className="text-sm text-slate-500 max-w-md">
              The neural engine is currently processing historical race data to generate comprehensive probability edge heatmaps and performance distribution graphs.
            </p>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
};
