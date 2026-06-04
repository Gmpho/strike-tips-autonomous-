import React, { useState } from 'react';
import { Flag, ChevronDown, ChevronUp, Medal, Users } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { ResultRace } from '../../types';

function PositionBadge({ position }: { position: string }) {
  const pos = position?.toLowerCase() || '';
  if (pos.includes('1st')) {
    return <span className="text-amber-500 font-black text-xs">1st</span>;
  }
  if (pos.includes('2nd')) {
    return <span className="text-slate-400 font-black text-xs">2nd</span>;
  }
  if (pos.includes('3rd')) {
    return <span className="text-amber-700 font-black text-xs">3rd</span>;
  }
  if (position) {
    return <span className="text-theme-secondary font-bold text-xs">{position}</span>;
  }
  return <span className="text-theme-secondary text-xs">—</span>;
}

function RaceCard({ race }: { race: ResultRace }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-theme-secondary/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Flag className="w-4 h-4 text-emerald-500 shrink-0" />
          <div className="text-left">
            <div className="text-sm font-bold text-theme-primary">{race.title || `${race.course} - ${race.time}`}</div>
            <div className="text-[10px] text-theme-secondary font-bold uppercase tracking-wider">{race.course}</div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-[10px] text-theme-secondary font-bold">{race.runners.length} runners</span>
          {expanded ? <ChevronUp className="w-4 h-4 text-theme-secondary" /> : <ChevronDown className="w-4 h-4 text-theme-secondary" />}
        </div>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className="border-t border-theme/50">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-theme/30">
                    <th className="text-left py-2 px-4 text-[9px] font-black text-theme-secondary uppercase tracking-widest">Pos</th>
                    <th className="text-left py-2 px-4 text-[9px] font-black text-theme-secondary uppercase tracking-widest">Horse</th>
                    <th className="text-right py-2 px-4 text-[9px] font-black text-theme-secondary uppercase tracking-widest">Odds</th>
                    <th className="text-right py-2 px-4 text-[9px] font-black text-theme-secondary uppercase tracking-widest">Form</th>
                  </tr>
                </thead>
                <tbody>
                  {race.runners.map((runner, idx) => (
                    <tr key={`${runner.name}-${idx}`} className="border-b border-theme/20 last:border-0 hover:bg-theme-secondary/20 transition-colors">
                      <td className="py-2 px-4"><PositionBadge position={runner.position} /></td>
                      <td className="py-2 px-4 font-bold text-theme-primary text-sm">{runner.name}</td>
                      <td className="py-2 px-4 text-right font-bold tabular text-theme-secondary">{runner.odds || '—'}</td>
                      <td className="py-2 px-4 text-right font-bold tabular text-theme-secondary">{runner.form || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export const ResultsView: React.FC = () => {
  const store = useHUD();
  const results = Array.isArray(store.results) ? store.results : [];

  const groupedByCourse = results.reduce<Record<string, ResultRace[]>>((acc, race) => {
    if (!acc[race.course]) acc[race.course] = [];
    acc[race.course].push(race);
    return acc;
  }, {});

  const courseNames = Object.keys(groupedByCourse).sort();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6"
    >
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-emerald-400 to-teal-500 bg-clip-text text-transparent">
          Race Results
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Latest finished races with positions
        </p>
      </div>

      {results.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-theme-secondary">
          <Flag className="w-8 h-8 mb-3 opacity-50" />
          <p className="text-sm font-bold">No results yet</p>
          <p className="text-xs opacity-70 mt-1">Data refreshes every 30s</p>
        </div>
      ) : (
        <div className="space-y-8">
          {courseNames.map(course => (
            <div key={course}>
              <div className="flex items-center gap-3 mb-4">
                <Medal className="w-4 h-4 text-emerald-400" />
                <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">{course}</h3>
                <span className="text-[10px] text-theme-secondary font-bold">{groupedByCourse[course].length} races</span>
              </div>
              <div className="space-y-3">
                {groupedByCourse[course].map((race, idx) => (
                  <RaceCard key={`${race.course}-${race.time}-${idx}`} race={race} />
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {results.length > 0 && (
        <div className="flex items-center gap-2 text-[10px] text-theme-secondary font-bold opacity-60">
          <Users className="w-3 h-3" />
          {results.reduce((sum, r) => sum + r.runners.length, 0)} runners across {results.length} races
        </div>
      )}
    </motion.div>
  );
};
