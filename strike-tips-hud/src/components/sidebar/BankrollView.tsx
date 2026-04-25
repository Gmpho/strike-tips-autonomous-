import React, { useEffect, useState } from 'react';
import { TrendingUp, DollarSign, Target, RotateCcw, Wallet } from 'lucide-react';
import { BETTING_ENDPOINTS } from '../../lib/api-prefixes';
import { motion } from 'framer-motion';

interface BetStats {
  totalBets: number;
  wins: number;
  losses: number;
  stakeTotal: number;
  payoutTotal: number;
  roi: number;
}

interface Bet {
  id: string;
  track: string;
  raceNumber: number;
  horse: string;
  odds: number;
  edgePercent: number;
  stake: number;
  confidence: string;
  settled: boolean;
  won?: boolean;
  payout?: number;
}

export const BankrollView: React.FC = () => {
  const [stats, setStats] = useState<BetStats | null>(null);
  const [bets, setBets] = useState<Bet[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, betsRes] = await Promise.all([
          fetch(BETTING_ENDPOINTS.stats),
          fetch(BETTING_ENDPOINTS.history)
        ]);
        
        if (!statsRes.ok || !betsRes.ok) {
          throw new Error('Failed to fetch data');
        }
        
        const statsData = await statsRes.json();
        const betsData = await betsRes.json();
        
        setStats(statsData);
        setBets(betsData.bets || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown error');
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 10000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-emerald-500 font-black uppercase tracking-widest text-xs">
          Syncing Bankroll...
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-red-500 font-black text-center bg-red-500/10 rounded-2xl border border-red-500/20">
        NETWORK ERROR: {error}
      </div>
    );
  }

  const winRate = stats && stats.totalBets > 0 ? (stats.wins / stats.totalBets * 100).toFixed(1) : '0.0';

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-8"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
            Bankroll & ROI
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            Financial Performance & Exposure
          </p>
        </div>
        <button 
          onClick={() => window.location.reload()}
          className="p-3 rounded-xl bg-theme-panel border border-theme text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary transition-all"
        >
          <RotateCcw className="w-5 h-5" />
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          { label: 'TOTAL BETS', value: stats?.totalBets || 0, icon: Target, color: 'text-blue-500' },
          { label: 'WIN RATE', value: `${winRate}%`, icon: TrendingUp, color: 'text-emerald-500' },
          { label: 'EXPOSURE', value: `R ${stats?.stakeTotal?.toFixed(2) || '0.00'}`, icon: Wallet, color: 'text-indigo-500' },
          { label: 'TOTAL ROI', value: `${(stats?.roi || 0) >= 0 ? '+' : ''}${stats?.roi?.toFixed(1) || '0.0'}%`, icon: TrendingUp, color: (stats?.roi || 0) >= 0 ? 'text-emerald-500' : 'text-red-500' },
        ].map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className={`text-xl font-black text-theme-primary mb-0.5 tabular ${stat.label === 'TOTAL ROI' ? (stats?.roi || 0) >= 0 ? 'text-emerald-500' : 'text-red-500' : ''}`}>
              {stat.value}
            </div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Recent Bets */}
      <div className="rounded-3xl bg-theme-panel border border-theme overflow-hidden backdrop-blur-2xl">
        <div className="px-6 py-4 border-b border-theme bg-theme-secondary/30 flex items-center gap-3">
          <DollarSign className="w-4 h-4 text-emerald-500" />
          <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest">Recent Executions</h3>
        </div>
        
        <div className="divide-y divide-theme overflow-y-auto max-h-[400px]">
          {bets.length === 0 ? (
            <div className="px-6 py-12 text-center text-theme-secondary font-black uppercase tracking-widest text-xs">
              Awaiting Market Entry...
            </div>
          ) : (
            bets.slice(0, 20).map((bet) => (
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
