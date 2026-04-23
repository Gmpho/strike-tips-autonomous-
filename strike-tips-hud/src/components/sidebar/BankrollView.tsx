import React, { useEffect, useState } from 'react';
import { TrendingUp, TrendingDown, DollarSign, Target, Activity, RotateCcw } from 'lucide-react';
import { BETTING_ENDPOINTS } from '../../lib/api-prefixes';

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
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-purple-500">Loading bankroll data...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-8 text-red-400">
        Error: {error}
      </div>
    );
  }

  const winRate = stats && stats.totalBets > 0 ? (stats.wins / stats.totalBets * 100).toFixed(1) : '0.0';

  return (
    <div className="p-8 animate-in fade-in duration-500">
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-black text-white tracking-tight">Bankroll & ROI</h2>
        <button 
          onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          <span className="text-sm">Refresh</span>
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <Target className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Total Bets</span>
          </div>
          <div className="text-3xl font-black text-white">{stats?.totalBets || 0}</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <TrendingUp className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Win Rate</span>
          </div>
          <div className="text-3xl font-black text-emerald-400">{winRate}%</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <DollarSign className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Stake Total</span>
          </div>
          <div className="text-3xl font-black text-white">R {stats?.stakeTotal?.toFixed(2) || '0.00'}</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            {((stats?.roi ?? 0) >= 0) ? (
              <TrendingUp className="w-4 h-4" />
            ) : (
              <TrendingDown className="w-4 h-4" />
            )}
            <span className="text-xs font-black uppercase tracking-wider">ROI</span>
          </div>
          <div className={`text-3xl font-black ${(stats?.roi || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
            {(stats?.roi || 0) >= 0 ? '+' : ''}{stats?.roi?.toFixed(1) || '0.0'}%
          </div>
        </div>
      </div>

      {/* Recent Bets */}
      <div className="bg-white/5 border border-white/10 rounded-2xl overflow-hidden">
        <div className="px-6 py-4 border-b border-white/10">
          <h3 className="text-sm font-black text-white uppercase tracking-wider">Recent Bets</h3>
        </div>
        <div className="divide-y divide-white/5 max-h-96 overflow-y-auto">
          {bets.length === 0 ? (
            <div className="px-6 py-8 text-center text-slate-500">
              No bets placed yet
            </div>
          ) : (
            bets.slice(0, 20).map((bet) => (
              <div key={bet.id} className="px-6 py-4 flex items-center justify-between hover:bg-white/5">
                <div className="flex items-center gap-4">
                  <div className={`w-2 h-2 rounded-full ${bet.settled ? (bet.won ? 'bg-emerald-500' : 'bg-red-500') : 'bg-amber-500'}`} />
                  <div>
                    <div className="text-sm font-bold text-white">{bet.horse}</div>
                    <div className="text-xs text-slate-500">{bet.track} - Race {bet.raceNumber}</div>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-mono text-white">R {bet.stake.toFixed(2)}</div>
                  <div className="text-xs text-slate-500">@{bet.odds}</div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
