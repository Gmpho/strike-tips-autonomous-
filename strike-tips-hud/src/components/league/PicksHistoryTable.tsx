import React, { useState, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Clock, Check, Trophy, Sparkles, ChevronLeft, ChevronRight, Search } from 'lucide-react';

export interface PickRowItem {
  race_id?: string;
  course?: string;
  race_number?: string | number;
  runner_number: number;
  runner_name?: string;
  pick_odds?: number | string;
  date?: string;
  off_iso?: string | null;
  settled?: boolean;
  won?: boolean;
  void?: boolean;
  void_reason?: string;
  finish_position?: number | null;
  points?: number;
  created_at?: string;
}

interface PicksHistoryTableProps {
  picks: PickRowItem[];
  title?: string;
  compact?: boolean;
  pageSize?: number;
}

function formatDateLabel(dateStr?: string, offIso?: string | null): string {
  const raw = dateStr || (offIso ? String(offIso).slice(0, 10) : '');
  if (!raw) return '—';
  const clean = raw.slice(0, 10);
  const today = new Date().toLocaleDateString('en-CA');
  const yesterday = new Date(Date.now() - 86400000).toLocaleDateString('en-CA');
  if (clean === today) return 'Today';
  if (clean === yesterday) return 'Yesterday';
  try {
    const d = new Date(`${clean}T12:00:00`);
    if (!isNaN(d.getTime())) {
      return d.toLocaleDateString('en-ZA', { day: 'numeric', month: 'short' });
    }
  } catch {}
  return clean;
}

function OutcomeBadge({ pick }: { pick: PickRowItem }) {
  if (pick.void) {
    // Refunded/abandoned race, or a pick that never resolved. Not a loss:
    // it does not count toward the strike rate.
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-slate-500/15 text-slate-300 border border-slate-500/30">
        Void{pick.void_reason ? ` · ${pick.void_reason}` : ''}
      </span>
    );
  }
  if (!pick.settled) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        <Clock className="w-3 h-3 animate-pulse" /> Pending
      </span>
    );
  }

  const pos = pick.finish_position;
  if (pos === 1) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-black bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 shadow-xs shadow-emerald-500/10">
        <Sparkles className="w-3 h-3 text-emerald-400" /> 1st
      </span>
    );
  }
  if (pos === 2) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-cyan-500/15 text-cyan-400 border border-cyan-500/30">
        2nd
      </span>
    );
  }
  if (pos === 3) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-amber-500/15 text-amber-400 border border-amber-500/30">
        3rd
      </span>
    );
  }
  if (pos === 4) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-purple-500/15 text-purple-400 border border-purple-500/30">
        4th
      </span>
    );
  }

  // Fallback for won without explicit finish position (e.g. legacy row)
  if (pick.won) {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
        <Check className="w-3 h-3" /> WON
      </span>
    );
  }

  return (
    <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-semibold bg-white/5 text-theme-secondary/60 border border-theme">
      LOST
    </span>
  );
}

export const PicksHistoryTable: React.FC<PicksHistoryTableProps> = ({
  picks,
  title,
  compact = false,
  pageSize = 10,
}) => {
  const [filter, setFilter] = useState<'all' | 'scored' | 'wins' | 'pending' | 'lost' | 'void'>('all');
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);

  // Filter counts
  const counts = useMemo(() => {
    let wins = 0;
    let scored = 0;
    let pending = 0;
    let lost = 0;
    let voided = 0;
    for (const p of picks) {
      if (p.void) {
        voided++;
      } else if (!p.settled) {
        pending++;
      } else if (p.won || (p.finish_position && p.finish_position <= 4)) {
        scored++;
        if (p.finish_position === 1 || (!p.finish_position && p.won)) wins++;
      } else {
        lost++;
      }
    }
    return { all: picks.length, scored, wins, pending, lost, voided };
  }, [picks]);

  // Filtered rows
  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return picks.filter(p => {
      // Status filter
      if (filter === 'void' && !p.void) return false;
      if (filter !== 'void' && p.void) return false;
      if (filter === 'pending' && p.settled) return false;
      if (filter === 'lost' && (!p.settled || p.won || (p.finish_position && p.finish_position <= 4))) return false;
      if (filter === 'scored' && (!p.settled || (!p.won && (!p.finish_position || p.finish_position > 4)))) return false;
      if (filter === 'wins' && (!p.settled || (!p.won && p.finish_position !== 1))) return false;

      // Text query
      if (q) {
        const horse = (p.runner_name || '').toLowerCase();
        const course = (p.course || '').toLowerCase();
        if (!horse.includes(q) && !course.includes(q)) return false;
      }
      return true;
    });
  }, [picks, filter, search]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, totalPages);
  const pageRows = useMemo(() => {
    const start = (currentPage - 1) * pageSize;
    return filtered.slice(start, start + pageSize);
  }, [filtered, currentPage, pageSize]);

  return (
    <div className={`w-full rounded-2xl bg-theme-panel border border-theme overflow-hidden backdrop-blur-xl shadow-lg ${compact ? 'p-2 sm:p-3' : 'p-4 sm:p-5'}`}>
      {/* Top Header & Search Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
        {title && (
          <h3 className="text-theme-primary font-bold text-base flex items-center gap-2">
            <Trophy className="w-4 h-4 text-purple-400" />
            {title}
            <span className="text-xs text-theme-secondary/60 font-normal">({counts.all})</span>
          </h3>
        )}

        <div className="flex items-center gap-2 flex-1 sm:justify-end">
          <div className="relative w-full sm:w-56">
            <Search className="w-3.5 h-3.5 text-theme-secondary/50 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              placeholder="Search horse or track..."
              value={search}
              onChange={e => {
                setSearch(e.target.value);
                setPage(1);
              }}
              className="w-full bg-theme-secondary/20 border border-theme rounded-xl pl-8 pr-3 py-1.5 text-xs text-theme-primary placeholder-theme-secondary/40 focus:outline-hidden focus:border-purple-500/50 transition-colors"
            />
          </div>
        </div>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1.5 overflow-x-auto pb-2 mb-3 custom-scrollbar text-xs">
        <button
          onClick={() => { setFilter('all'); setPage(1); }}
          className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
            filter === 'all'
              ? 'bg-purple-500/20 text-purple-300 border border-purple-500/40 shadow-xs'
              : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
          }`}>
          All ({counts.all})
        </button>

        <button
          onClick={() => { setFilter('scored'); setPage(1); }}
          className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
            filter === 'scored'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-xs'
              : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
          }`}>
          Scored 1st–4th ({counts.scored})
        </button>

        <button
          onClick={() => { setFilter('wins'); setPage(1); }}
          className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
            filter === 'wins'
              ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 shadow-xs'
              : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
          }`}>
          Wins 🥇 ({counts.wins})
        </button>

        {counts.pending > 0 && (
          <button
            onClick={() => { setFilter('pending'); setPage(1); }}
            className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
              filter === 'pending'
                ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40 shadow-xs'
                : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
            }`}>
            Pending ⏳ ({counts.pending})
          </button>
        )}

        <button
          onClick={() => { setFilter('lost'); setPage(1); }}
          className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
            filter === 'lost'
              ? 'bg-white/15 text-theme-primary border border-theme shadow-xs'
              : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
          }`}>
          Unplaced ({counts.lost})
        </button>

        {counts.voided > 0 && (
          <button
            onClick={() => { setFilter('void'); setPage(1); }}
            className={`px-3 py-1 rounded-lg font-semibold transition-all whitespace-nowrap ${
              filter === 'void'
                ? 'bg-slate-500/20 text-slate-200 border border-slate-500/40 shadow-xs'
                : 'text-theme-secondary/70 hover:text-theme-primary hover:bg-white/5 border border-transparent'
            }`}>
            Void ({counts.voided})
          </button>
        )}
      </div>

      {/* Main Table */}
      {filtered.length === 0 ? (
        <div className="py-8 text-center text-sm text-theme-secondary/60 bg-theme-secondary/10 rounded-xl border border-theme">
          No picks match the selected filter.
        </div>
      ) : (
        <div className="overflow-x-auto rounded-xl border border-theme bg-theme-panel/40">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-theme bg-theme-secondary/30 text-theme-secondary text-[10px] uppercase font-black tracking-wider">
                <th className="py-2.5 px-3">Date</th>
                <th className="py-2.5 px-3">Meeting & Race</th>
                <th className="py-2.5 px-3">Selection</th>
                <th className="py-2.5 px-3 text-right">Taken Odds</th>
                <th className="py-2.5 px-3 text-center">Outcome</th>
                <th className="py-2.5 px-3 text-right">Points</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-theme/40">
              <AnimatePresence mode="popLayout">
                {pageRows.map((pick, idx) => {
                  const pts = pick.points || 0;
                  const isScoring = pick.settled && (pick.won || (pick.finish_position && pick.finish_position <= 4));
                  const oddsNum = Number(pick.pick_odds);

                  return (
                    <motion.tr
                      key={`${pick.race_id || pick.course}-${pick.runner_number}-${idx}`}
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      className="hover:bg-theme-secondary/20 transition-colors">
                      {/* Date */}
                      <td className="py-2.5 px-3 whitespace-nowrap text-theme-secondary/70 font-medium">
                        {formatDateLabel(pick.date, pick.off_iso)}
                      </td>

                      {/* Course & Race */}
                      <td className="py-2.5 px-3 whitespace-nowrap">
                        <div className="flex items-center gap-1.5">
                          <span className="font-bold text-theme-primary">{pick.course || 'Race'}</span>
                          <span className="text-[10px] font-black px-1.5 py-0.5 rounded-md bg-purple-500/10 text-purple-300 border border-purple-500/20">
                            R{pick.race_number ?? '?'}
                          </span>
                        </div>
                      </td>

                      {/* Selection (Saddle Badge + Horse) */}
                      <td className="py-2.5 px-3">
                        <div className="flex items-center gap-2">
                          <span className="w-6 h-6 rounded-lg bg-theme-secondary/40 border border-theme text-theme-primary font-bold text-[11px] flex items-center justify-center shrink-0">
                            #{pick.runner_number}
                          </span>
                          <span className="font-bold text-theme-primary truncate max-w-[140px] sm:max-w-[220px]">
                            {pick.runner_name || `Runner #${pick.runner_number}`}
                          </span>
                        </div>
                      </td>

                      {/* Odds */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap">
                        <span className="font-tabular font-bold text-theme-secondary px-2 py-0.5 rounded-md bg-theme-secondary/20 border border-theme">
                          {!isNaN(oddsNum) && oddsNum > 0 ? oddsNum.toFixed(2) : '—'}
                        </span>
                      </td>

                      {/* Outcome Badge */}
                      <td className="py-2.5 px-3 text-center whitespace-nowrap">
                        <OutcomeBadge pick={pick} />
                      </td>

                      {/* Points */}
                      <td className="py-2.5 px-3 text-right whitespace-nowrap">
                        {isScoring && pts > 0 ? (
                          <span className="font-black text-emerald-400 font-tabular bg-emerald-500/10 px-2 py-0.5 rounded-md border border-emerald-500/20">
                            +{pts} pts
                          </span>
                        ) : pick.settled ? (
                          <span className="text-theme-secondary/50 font-tabular">0</span>
                        ) : (
                          <span className="text-theme-secondary/40 font-tabular">—</span>
                        )}
                      </td>
                    </motion.tr>
                  );
                })}
              </AnimatePresence>
            </tbody>
          </table>
        </div>
      )}

      {/* Pagination Footer */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-theme text-xs text-theme-secondary/70">
          <span>
            Showing {(currentPage - 1) * pageSize + 1}–{Math.min(currentPage * pageSize, filtered.length)} of {filtered.length}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              disabled={currentPage <= 1}
              onClick={() => setPage(p => Math.max(1, p - 1))}
              className="p-1 rounded-lg border border-theme bg-theme-secondary/20 text-theme-primary hover:bg-theme-secondary/40 disabled:opacity-30 disabled:pointer-events-none transition-all">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2 font-tabular font-bold text-theme-primary">
              {currentPage} / {totalPages}
            </span>
            <button
              disabled={currentPage >= totalPages}
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              className="p-1 rounded-lg border border-theme bg-theme-secondary/20 text-theme-primary hover:bg-theme-secondary/40 disabled:opacity-30 disabled:pointer-events-none transition-all">
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

