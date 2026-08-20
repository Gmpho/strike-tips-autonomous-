import React, { useEffect, useState } from 'react';
import { Ticket, Coins, Trophy, Calendar, Activity, Loader2, Star } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../hooks/useHUD';
import { apiFetch } from '../lib/api-fetch';

interface CombinationSelection {
  race: number;
  banker: number;
  savers: number[];
}

interface ExoticPlay {
  pool: string;
  legs: number[];
  combinations: CombinationSelection[];
  estimated_combinations: number;
  estimated_dividend: number;
  reasoning?: string;
  _track?: string;
}

export const ExoticsView: React.FC = () => {
  const { betHistory } = useHUD();
  const [activePlays, setActivePlays] = useState<ExoticPlay[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'active' | 'history'>('active');

  useEffect(() => {
    let active = true;
    const fetchExotics = async () => {
      try {
        const res = await apiFetch('/api/racing/exotics');
        if (res.ok && active) {
          const data = await res.json();
          setActivePlays(data || []);
        }
      } catch (err) {
        console.error('Failed to fetch exotics:', err);
      } finally {
        if (active) setLoading(false);
      }
    };
    fetchExotics();
    return () => {
      active = false;
    };
  }, []);

  // Filter historical exotic bets from global ledger
  const exoticHistory = betHistory.filter(b => b.confidence === 'EXOTIC');

  // Calculate Exotic stats
  const totalStaked = exoticHistory.reduce((sum, b) => sum + b.stake, 0);
  const totalPayout = exoticHistory.reduce((sum, b) => sum + (b.payout || 0), 0);
  const totalPnL = totalPayout - totalStaked;
  const exoticRoi = totalStaked > 0 ? (totalPnL / totalStaked) * 100 : 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-8"
    >
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h2 className="text-2xl font-black bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent flex items-center gap-2">
            <Ticket className="w-7 h-7 text-purple-400" />
            Exotic Betting Hub
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            Multi-Leg Permutation & Coverage Analysis
          </p>
        </div>

        {/* Tab Controls */}
        <div className="flex border border-theme p-1 rounded-2xl bg-theme-panel shrink-0">
          <button
            onClick={() => setActiveTab('active')}
            className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer ${
              activeTab === 'active'
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-theme-secondary hover:text-theme-primary'
            }`}
          >
            Active Plays
          </button>
          <button
            onClick={() => setActiveTab('history')}
            className={`px-4 py-2 rounded-xl text-xs font-black uppercase tracking-wider transition-all cursor-pointer ${
              activeTab === 'history'
                ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                : 'text-theme-secondary hover:text-theme-primary'
            }`}
          >
            Settle Ledger
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'active' ? (
          <motion.div
            key="active-plays"
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className="space-y-6"
          >
            {loading ? (
              <div className="flex flex-col items-center justify-center p-12 bg-theme-panel border border-theme rounded-3xl min-h-[300px]">
                <Loader2 className="w-8 h-8 text-purple-400 animate-spin mb-3" />
                <p className="text-xs text-theme-secondary uppercase tracking-widest font-black">Reading exotics memory...</p>
              </div>
            ) : activePlays.length === 0 ? (
              <div className="flex flex-col items-center justify-center p-12 bg-theme-panel border border-theme rounded-3xl min-h-[300px]">
                <Activity className="w-12 h-12 text-slate-600 mb-3" />
                <p className="text-sm font-bold text-theme-primary mb-1 uppercase tracking-wide">No Active Pools Found</p>
                <p className="text-xs text-theme-secondary text-center max-w-md font-bold">
                  Exotic play blueprints are automatically generated during the 05:00 daily scan if pool structural details are found in the Computaform PDF sheets.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 xl:grid-cols-2 gap-6">
                {activePlays.map((play, index) => {
                  const estCost = play.combinations.length * 1.20; // Suggested R1.20 unit cost
                  return (
                    <motion.div
                      key={index}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: index * 0.05 }}
                      className="hud-card group p-6 border border-theme bg-theme-secondary rounded-3xl relative overflow-hidden flex flex-col justify-between hover:shadow-[0_0_30px_rgba(168,85,247,0.1)] transition-all"
                    >
                      <div>
                        {/* Pool Header */}
                        <div className="flex justify-between items-start mb-6">
                          <div>
                            <span className="text-[9px] font-black text-purple-400 bg-purple-500/10 px-2 py-0.5 border border-purple-500/30 rounded uppercase tracking-wider">
                              {play._track || 'TODAY'}
                            </span>
                            <h3 className="text-2xl font-black text-theme-primary tracking-tighter uppercase mt-1">
                              {play.pool}
                            </h3>
                          </div>
                          <div className="text-right">
                            <div className="text-[9px] text-theme-secondary font-black">EST. DIVIDEND</div>
                            <div className="text-xl font-black text-emerald-400 tabular leading-none mt-1">
                              R{play.estimated_dividend?.toLocaleString()}
                            </div>
                          </div>
                        </div>

                        {/* Combinations Blueprint */}
                        <div className="bg-theme-panel rounded-2xl p-4 border border-theme mb-6">
                          <h4 className="text-[10px] text-theme-secondary font-black tracking-widest uppercase mb-3 flex items-center gap-1.5">
                            <Activity className="w-3.5 h-3.5 text-purple-400" />
                            Multi-Leg Structure
                          </h4>
                          <div className="space-y-3">
                            {play.combinations.map((combo, idx) => (
                              <div key={idx} className="flex items-center gap-3 border-b border-white/5 pb-2 last:border-b-0 last:pb-0">
                                <div className="text-[10px] font-black text-purple-400 w-12 shrink-0">LEG {idx + 1}</div>
                                <div className="text-[9px] text-slate-500 uppercase w-14 shrink-0 font-bold">RACE {combo.race}</div>
                                <div className="flex flex-wrap gap-1.5 flex-1 items-center">
                                  {/* Banker */}
                                  <span className="text-[11px] font-black text-amber-300 bg-amber-500/10 px-2 py-0.5 border border-amber-500/30 rounded-lg flex items-center gap-1">
                                    <Star className="w-3 h-3 fill-amber-300" />
                                    Horse {combo.banker} (Banker)
                                  </span>
                                  {/* Savers */}
                                  {combo.savers.map(s => (
                                    <span key={s} className="text-[11px] font-black text-slate-300 bg-white/5 px-2 py-0.5 border border-theme rounded-lg">
                                      Horse {s} (Saver)
                                    </span>
                                  ))}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>

                      {/* Summary Metrics */}
                      <div className="flex justify-between items-center pt-4 border-t border-white/5 mt-auto">
                        <div className="flex gap-4">
                          <div>
                            <div className="text-[9px] text-theme-secondary font-black uppercase">Permutations</div>
                            <div className="text-sm font-black text-theme-primary tabular">{play.combinations.length}</div>
                          </div>
                          <div>
                            <div className="text-[9px] text-theme-secondary font-black uppercase">Est. Cost</div>
                            <div className="text-sm font-black text-theme-primary tabular">R{estCost.toFixed(2)}</div>
                          </div>
                        </div>
                        <div className="text-[10px] text-slate-400 italic max-w-[50%] text-right font-bold">
                          {play.reasoning || "AI analyzed combination."}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            )}
          </motion.div>
        ) : (
          <motion.div
            key="history-ledger"
            initial={{ opacity: 0, x: 10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -10 }}
            className="space-y-6"
          >
            {/* KPI metrics row */}
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <div className="p-4 rounded-2xl bg-theme-panel border border-theme">
                <Coins className="w-4 h-4 text-purple-400 mb-3" />
                <div className="text-xl font-black text-theme-primary mb-0.5 tabular">R{totalStaked.toFixed(2)}</div>
                <div className="text-[9px] text-theme-secondary font-black uppercase">Total Exotic Staked</div>
              </div>
              <div className="p-4 rounded-2xl bg-theme-panel border border-theme">
                <Trophy className="w-4 h-4 text-emerald-400 mb-3" />
                <div className="text-xl font-black text-theme-primary mb-0.5 tabular">R{totalPayout.toFixed(2)}</div>
                <div className="text-[9px] text-theme-secondary font-black uppercase">Total Returns</div>
              </div>
              <div className="p-4 rounded-2xl bg-theme-panel border border-theme">
                <Trophy className="w-4 h-4 text-purple-400 mb-3" />
                <div className={`text-xl font-black mb-0.5 tabular ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {totalPnL >= 0 ? '+' : ''}R{totalPnL.toFixed(2)}
                </div>
                <div className="text-[9px] text-theme-secondary font-black uppercase">Net Profit/Loss</div>
              </div>
              <div className="p-4 rounded-2xl bg-theme-panel border border-theme">
                <Activity className="w-4 h-4 text-amber-500 mb-3" />
                <div className={`text-xl font-black mb-0.5 tabular ${totalPnL >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                  {exoticRoi.toFixed(1)}%
                </div>
                <div className="text-[9px] text-theme-secondary font-black uppercase">Exotics ROI</div>
              </div>
            </div>

            {/* Historic Exotics Table */}
            <div className="p-6 rounded-2xl bg-theme-panel border border-theme">
              <div className="flex items-center gap-3 mb-6">
                <Calendar className="w-4 h-4 text-purple-400" />
                <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">Exotic Bet History</h3>
              </div>
              {exoticHistory.length === 0 ? (
                <p className="text-xs text-theme-secondary font-bold">No historic exotic bets recorded.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="border-b border-theme text-theme-secondary font-black uppercase text-[10px]">
                        <th className="py-3 px-2">Ticket ID</th>
                        <th className="py-3 px-2">Track</th>
                        <th className="py-3 px-2">Pool Description</th>
                        <th className="py-3 px-2 text-right">Stake</th>
                        <th className="py-3 px-2 text-right">Payout</th>
                        <th className="py-3 px-2 text-center">Status</th>
                      </tr>
                    </thead>
                    <tbody className="text-theme-primary font-mono font-bold">
                      {exoticHistory.map(bet => (
                        <tr key={bet.id} className="border-b border-theme/50 hover:bg-white/2 transition-colors">
                          <td className="py-3 px-2 truncate max-w-[120px]">{bet.id}</td>
                          <td className="py-3 px-2 uppercase">{bet.track}</td>
                          <td className="py-3 px-2 text-purple-300">{bet.horse}</td>
                          <td className="py-3 px-2 text-right tabular">R{bet.stake.toFixed(2)}</td>
                          <td className="py-3 px-2 text-right tabular text-emerald-400">
                            {bet.settled && bet.won ? `R${bet.payout?.toFixed(2)}` : '-'}
                          </td>
                          <td className="py-3 px-2 text-center">
                            <span className={`text-[10px] px-2 py-0.5 rounded font-black border uppercase ${
                              bet.settled 
                                ? bet.won 
                                  ? 'border-emerald-500/30 text-emerald-400 bg-emerald-500/10' 
                                  : 'border-red-500/30 text-red-400 bg-red-500/10'
                                : 'border-amber-500/30 text-amber-400 bg-amber-500/10'
                            }`}>
                              {bet.settled ? bet.won ? 'WON' : 'LOST' : 'OPEN'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};
