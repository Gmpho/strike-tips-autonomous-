import React from 'react';
import { TrendingUp, DollarSign, Target, RotateCcw, Wallet, Landmark, ChevronDown } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { BetRecord } from '../../types';

type ExecFilter = 'ALL' | 'WON' | 'LOST' | 'OPEN';

function betStatus(bet: BetRecord): 'WON' | 'LOST' | 'PENDING' | 'VOID' | 'EXPIRED' {
  const s = String(bet.status || '').toUpperCase();
  if (s === 'WON' || s === 'LOST' || s === 'VOID' || s === 'EXPIRED' || s === 'PENDING') return s;
  if (bet.settled) return bet.won ? 'WON' : 'LOST';
  return 'PENDING';
}

function betPnl(bet: BetRecord): number | null {
  const st = betStatus(bet);
  if (st === 'WON') return (bet.payout ?? 0) - bet.stake;
  if (st === 'LOST') return -bet.stake;
  return null;
}

function fmtTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function dayLabel(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return 'Unknown date';
  const now = new Date();
  const day = (x: Date) => `${x.getFullYear()}-${x.getMonth()}-${x.getDate()}`;
  if (day(d) === day(now)) return 'Today';
  const y = new Date(now);
  y.setDate(y.getDate() - 1);
  if (day(d) === day(y)) return 'Yesterday';
  return d.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: d.getFullYear() === now.getFullYear() ? undefined : 'numeric' });
}

const STATUS_STYLE: Record<string, { dot: string; pill: string; label: string }> = {
  WON: { dot: 'bg-emerald-500 shadow-emerald-500', pill: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', label: 'WON' },
  LOST: { dot: 'bg-red-500 shadow-red-500', pill: 'bg-red-500/15 text-red-400 border-red-500/30', label: 'LOST' },
  PENDING: { dot: 'bg-amber-500 shadow-amber-500 animate-pulse', pill: 'bg-amber-500/15 text-amber-400 border-amber-500/30', label: 'OPEN' },
  VOID: { dot: 'bg-slate-500 shadow-slate-500', pill: 'bg-slate-500/15 text-slate-400 border-slate-500/30', label: 'VOID' },
  EXPIRED: { dot: 'bg-slate-600 shadow-slate-600', pill: 'bg-slate-600/15 text-slate-500 border-slate-600/30', label: 'EXPIRED' },
};

const FILTERS: { key: ExecFilter; label: string }[] = [
  { key: 'ALL', label: 'All' },
  { key: 'WON', label: 'Wins' },
  { key: 'LOST', label: 'Losses' },
  { key: 'OPEN', label: 'Open' },
];

const PAGE = 30;

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

  // Settled-only win rate (totalBets includes the open backlog).
  const settledCount = (betStats?.wins ?? 0) + (betStats?.losses ?? 0);
  const winRate = settledCount > 0 ? ((betStats?.wins ?? 0) / settledCount * 100).toFixed(1) : '0.0';

  // Ledger: newest-first, filterable, day-grouped, paginated.
  const [execFilter, setExecFilter] = React.useState<ExecFilter>('ALL');
  const [execShown, setExecShown] = React.useState<number>(PAGE);

  const sortedExecs = React.useMemo(
    () => [...(betHistory || [])].sort(
      (a, b) => new Date(b.placedAt).getTime() - new Date(a.placedAt).getTime(),
    ),
    [betHistory],
  );

  const filteredExecs = React.useMemo(() => {
    if (execFilter === 'ALL') return sortedExecs;
    if (execFilter === 'OPEN') return sortedExecs.filter((b) => betStatus(b) === 'PENDING');
    return sortedExecs.filter((b) => betStatus(b) === execFilter);
  }, [sortedExecs, execFilter]);

  const visible = filteredExecs.slice(0, execShown);

  const grouped = React.useMemo(() => {
    const groups: { day: string; bets: BetRecord[] }[] = [];
    for (const bet of visible) {
      const day = dayLabel(bet.placedAt);
      const last = groups[groups.length - 1];
      if (last && last.day === day) last.bets.push(bet);
      else groups.push({ day, bets: [bet] });
    }
    return groups;
  }, [visible]);

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-3.5 sm:p-6 space-y-6 sm:space-y-8 w-full"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl sm:text-2xl font-bold bg-linear-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent flex items-center gap-2 sm:gap-3">
            Bankroll & ROI
            {bankroll?.paperMode && (
              <span className="text-[10px] sm:text-xs font-black px-2 py-0.5 rounded-full bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 uppercase tracking-widest">
                PAPER
              </span>
            )}
          </h2>
          <p className="text-[10px] sm:text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
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
            <span className="text-4xl font-black text-theme-primary tracking-tighter uppercase">
              {bankroll && bankroll.paperMode !== undefined
                ? `R ${bankroll.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                : 'R —'}
            </span>
          </div>
          {/* Ledger split: active betting bank vs the untouched other ledger.
              Only render once paperMode is known — a stale cached bankroll
              (paperMode undefined) would fabricate a "LIVE R1,000" line. */}
          {bankroll && bankroll.paperMode !== undefined && (bankroll.paperBalance !== undefined || bankroll.realBalance !== undefined) && (
            <div className="mt-3 text-[10px] font-bold text-theme-secondary">
              {bankroll.paperMode ? (
                <span>Betting bank (paper): <span className="text-cyan-400 font-mono">R{(bankroll.paperBalance ?? bankroll.balance).toFixed(2)}</span>
                {bankroll.realBalance !== undefined && (
                  <span className="opacity-70"> · Real funds: <span className="font-mono">R{bankroll.realBalance.toFixed(2)}</span> (untouched)</span>
                )}</span>
              ) : (
                <span>Betting bank (live): <span className="text-emerald-400 font-mono">R{bankroll.balance.toFixed(2)}</span>
                {bankroll.paperBalance !== undefined && (
                  <span className="opacity-70"> · Paper bank: <span className="font-mono">R{bankroll.paperBalance.toFixed(2)}</span> (simulation)</span>
                )}</span>
              )}
            </div>
          )}
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
        <div className="px-6 py-4 border-b border-theme bg-theme-secondary/30 flex flex-wrap items-center gap-3">
          <DollarSign className="w-4 h-4 text-emerald-500" />
          <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest mr-auto">Recent Executions</h3>
          <div className="flex items-center gap-1 bg-black/20 rounded-xl p-1 border border-white/5">
            {FILTERS.map((f) => (
              <button
                key={f.key}
                type="button"
                onClick={() => { setExecFilter(f.key); setExecShown(PAGE); }}
                className={`px-2.5 py-1 rounded-lg text-[10px] font-black uppercase tracking-wider transition-all ${
                  execFilter === f.key ? 'bg-purple-500/25 text-purple-200' : 'text-theme-secondary hover:text-theme-primary'
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        <div className="divide-y divide-theme overflow-y-auto max-h-[460px] min-h-[100px]">
          {visible.length === 0 ? (
            <div className="px-6 py-12 text-center text-theme-secondary font-black uppercase tracking-widest text-xs">
              {sortedExecs.length === 0 ? 'Awaiting Market Entry...' : `No ${FILTERS.find((f) => f.key === execFilter)?.label.toLowerCase()} executions.`}
            </div>
          ) : (
            grouped.map((group) => (
              <div key={group.day}>
                <div className="px-6 pt-3 pb-1 text-[9px] font-black text-theme-secondary/70 uppercase tracking-[0.2em] sticky top-0 bg-theme-panel/95 backdrop-blur z-10">
                  {group.day}
                </div>
                {group.bets.map((bet) => {
                  const st = betStatus(bet);
                  const sty = STATUS_STYLE[st];
                  const pnl = betPnl(bet);
                  return (
                    <motion.div
                      key={bet.id}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="px-6 py-3.5 flex items-center justify-between gap-3 hover:bg-theme-secondary/50 transition-colors group"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className={`w-2 h-2 rounded-full shadow-[0_0_10px] shrink-0 ${sty.dot}`} />
                        <div className="min-w-0">
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="text-sm font-black text-theme-primary uppercase tracking-tighter truncate group-hover:text-emerald-500 transition-colors">
                              {bet.horse}
                            </span>
                            <span className={`px-1.5 py-px text-[8px] font-black rounded border uppercase shrink-0 ${sty.pill}`}>
                              {sty.label}
                            </span>
                          </div>
                          <div className="text-[10px] text-theme-secondary font-bold uppercase tracking-widest truncate">
                            {bet.track} • RACE {bet.raceNumber} • {fmtTime(bet.placedAt)}
                          </div>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-black text-theme-primary tabular">R {bet.stake.toFixed(2)}</div>
                        <div className="text-[10px] font-black tabular">
                          {pnl !== null ? (
                            <span className={pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                              {pnl >= 0 ? '+' : ''}R{pnl.toFixed(2)}
                            </span>
                          ) : (
                            <span className="text-theme-secondary">@{bet.odds}</span>
                          )}
                        </div>
                      </div>
                    </motion.div>
                  );
                })}
              </div>
            ))
          )}
        </div>
        {visible.length < filteredExecs.length && (
          <button
            type="button"
            onClick={() => setExecShown((n) => n + PAGE)}
            className="w-full py-3 flex items-center justify-center gap-1.5 text-[11px] font-black uppercase tracking-widest text-purple-400 hover:text-purple-300 hover:bg-purple-500/5 transition-all border-t border-theme"
          >
            Show more ({filteredExecs.length - visible.length} older) <ChevronDown className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
    </motion.div>
  );
};
