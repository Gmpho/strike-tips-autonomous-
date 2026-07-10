import React from 'react';
import { TrendingUp, DollarSign, Target, RotateCcw, Wallet, Landmark } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const BankrollView: React.FC = () => {
  const { bankroll, betStats, betHistory, systemHealth } = useHUD();

  if (systemHealth.status === 'OFFLINE' && !bankroll?.balance) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-emerald-500 font-black uppercase tracking-widest text-xs">
          Syncing Bankroll...
        </div>
      </div>
    );
  }

  const winRate = betStats && betStats.totalBets > 0 ? (betStats.wins / betStats.totalBets * 100).toFixed(1) : '0.0';

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-8"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent flex items-center gap-3">
            Bankroll & ROI
            {bankroll?.paperMode && (
              <span className="text-xs font-black px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 uppercase tracking-widest">
                PAPER
              </span>
            )}
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            {bankroll?.paperMode ? `Virtual Balance: R${(bankroll.paperBalance ?? 0).toFixed(2)}` : 'Financial Performance & Exposure'}
          </p>
        </div>
        <button 
          onClick={() => window.location.reload()}
          aria-label="Reload page"
          className="p-3 rounded-xl bg-theme-panel border border-theme text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary transition-all"
        >
          <RotateCcw className="w-5 h-5" />
        </button>
      </div>

      {/* Main Bankroll Display */}
      <div className="p-8 rounded-4xl bg-linear-to-br from-indigo-500/10 to-purple-500/10 border border-indigo-500/20  relative overflow-hidden group">
        <div className="absolute top-0 right-0 p-8 opacity-10 group-hover:scale-110 transition-transform duration-700">
          <Landmark className="w-24 h-24 text-indigo-400" />
        </div>
        <div className="relative z-10">
          <div className="text-[10px] font-black text-indigo-400 uppercase tracking-[0.4em] mb-2">Current Bankroll</div>
          <div className="flex items-baseline gap-3">
            <span className="text-4xl font-black text-theme-primary tracking-tighter uppercase">R {bankroll?.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }) || '0.00'}</span>
          </div>
          <div className="mt-4 flex gap-6">
            <div>
              <div className="text-[9px] font-bold text-theme-secondary uppercase mb-0.5">Daily Limit</div>
              <div className="text-sm font-black text-theme-primary tracking-tight">R {bankroll?.dailyLimit.toFixed(2) || '0.00'}</div>
            </div>
            <div>
              <div className="text-[9px] font-bold text-theme-secondary uppercase mb-0.5">Max Stake</div>
              <div className="text-sm font-black text-theme-primary tracking-tight">R {bankroll?.maxStake.toFixed(2) || '0.00'}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'TOTAL BETS', value: betStats?.totalBets || 0, icon: Target, color: 'text-blue-500' },
          { label: 'WIN RATE', value: `${winRate}%`, icon: TrendingUp, color: 'text-emerald-500' },
          { label: 'EXPOSURE', value: `R ${bankroll?.totalExposure?.toFixed(2) || '0.00'}`, icon: Wallet, color: 'text-indigo-500' },
          { label: 'TOTAL ROI', value: `${(betStats?.roi || 0) >= 0 ? '+' : ''}${betStats?.roi?.toFixed(1) || '0.0'}%`, icon: TrendingUp, color: (betStats?.roi || 0) >= 0 ? 'text-emerald-500' : 'text-red-500' },
        ].map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme ">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className={`text-xl font-black text-theme-primary mb-0.5 tabular ${stat.label === 'TOTAL ROI' ? (betStats?.roi || 0) >= 0 ? 'text-emerald-500' : 'text-red-500' : ''}`}>
              {stat.value}
            </div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Recent Bets */}
      <div className="rounded-3xl bg-theme-panel border border-theme overflow-hidden ">
        <div className="px-6 py-4 border-b border-theme bg-theme-secondary/30 flex items-center gap-3">
          <DollarSign className="w-4 h-4 text-emerald-500" />
          <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest">Recent Executions</h3>
        </div>
        
        <div className="divide-y divide-theme overflow-y-auto max-h-[400px]">
          {betHistory.length === 0 ? (
            <div className="px-6 py-12 text-center text-theme-secondary font-black uppercase tracking-widest text-xs">
              Awaiting Market Entry...
            </div>
          ) : (
            betHistory.slice(0, 20).map((bet) => (
              <motion.div 
                key={bet.id} 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-6 py-4 flex items-center justify-between hover:bg-theme-secondary/50 transition-colors group"
              >
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full shadow-[0_0_10px] ${bet.settled ? (bet.won ? 'bg-emerald-500 shadow-emerald-500' : 'bg-red-500 shadow-red-500') : 'bg-amber-500 shadow-amber-500 animate-pulse'}`} />
                  <div>
                    <div className="text-sm font-black text-theme-primary uppercase tracking-tighter group-hover:text-emerald-500 transition-colors">
                      {bet.horse}
                    </div>
                    <div className="text-[10px] text-theme-secondary font-bold uppercase tracking-widest">
                      {bet.track} • RACE {bet.raceNumber}
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-black text-theme-primary tabular">R {bet.stake.toFixed(2)}</div>
                  <div className="text-[10px] text-theme-secondary font-black tabular">@{bet.odds}</div>
                </div>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </motion.div>
  );
};
