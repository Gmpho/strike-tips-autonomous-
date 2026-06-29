import React, { useState } from 'react';
import { Flag, ChevronDown, ChevronUp, Medal, Users } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import type { ResultRace } from '../../types';
import { getFullCourseName } from '../../lib/course-names';

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
    <div className="rounded-2xl bg-theme-panel border border-theme sidebar-card overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between p-4 hover:bg-theme-secondary/20 transition-colors"
      >
        <div className="flex items-center gap-3">
          <Flag className="w-4 h-4 text-emerald-500 shrink-0" />
          <div className="text-left">
            <div className="text-sm font-bold text-theme-primary">{race.title || `${getFullCourseName(race.course)} - ${race.time}`}</div>
            <div className="text-[10px] text-theme-secondary font-bold uppercase tracking-wider">{getFullCourseName(race.course)}</div>
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
  
  const [searchQuery, setSearchQuery] = useState('');
  const [collapsedCourses, setCollapsedCourses] = useState<Record<string, boolean>>({});

  const filteredResults = results.filter((race) => {
    const query = searchQuery.toLowerCase();
    const courseMatches = 
      race.course.toLowerCase().includes(query) ||
      getFullCourseName(race.course).toLowerCase().includes(query);
    const titleMatches = race.title?.toLowerCase().includes(query);
    const runnersMatch = race.runners.some(runner => runner.name.toLowerCase().includes(query));
    return courseMatches || titleMatches || runnersMatch;
  });

  const groupedByCourse = filteredResults.reduce<Record<string, ResultRace[]>>((acc, race) => {
    if (!acc[race.course]) acc[race.course] = [];
    acc[race.course].push(race);
    return acc;
  }, {});

  const courseNames = Object.keys(groupedByCourse).sort();

  const toggleCourse = (course: string) => {
    setCollapsedCourses(prev => ({
      ...prev,
      [course]: !prev[course]
    }));
  };

  const isCourseExpanded = (course: string, index: number) => {
    const explicitState = collapsedCourses[course];
    if (explicitState !== undefined) {
      return explicitState;
    }
    if (searchQuery.trim() !== '') {
      return true;
    }
    return index === 0;
  };

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-6 h-full flex flex-col"
    >
      {/* ── Header ── */}
      <div className="shrink-0 space-y-3">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-emerald-400 to-teal-500 bg-clip-text text-transparent">
            Race Results
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            Latest finished races with positions
          </p>
        </div>

        {results.length > 0 && (
          <div className="flex items-center gap-2 text-[10px] text-theme-secondary font-bold">
            <Users className="w-3 h-3" />
            {results.reduce((sum, r) => sum + r.runners.length, 0)} runners across {results.length} races
          </div>
        )}

        {/* Search Input */}
        {results.length > 0 && (
          <div className="relative">
            <input
              type="text"
              placeholder="Search course or runner..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-3 py-2 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 transition-all font-semibold"
            />
          </div>
        )}
      </div>

      {results.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <Flag className="w-8 h-8 mb-3 opacity-50" />
          <p className="text-sm font-bold">No results yet</p>
          <p className="text-xs opacity-70 mt-1">Data refreshes every 30s</p>
        </div>
      ) : filteredResults.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center text-theme-secondary">
          <div className="p-6 rounded-3xl bg-white/5 border border-white/10 flex flex-col items-center gap-4">
            <Flag className="w-10 h-10 opacity-30" />
            <div className="text-center space-y-1">
              <p className="text-sm font-bold text-theme-primary/60">No Results Match Filters</p>
              <p className="text-xs text-theme-secondary">
                Try adjusting your search query
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar scroll-container pr-1 -mr-1">
          <div className="space-y-6 pb-2">
            {courseNames.map((course, index) => {
              const expanded = isCourseExpanded(course, index);
              return (
                <div key={course} className="space-y-1">
                  {/* Collapsible Accordion Header */}
                  <button
                    onClick={() => toggleCourse(course)}
                    className="w-full flex items-center justify-between py-2 text-left hover:bg-white/5 rounded-xl px-2 -mx-2 transition-colors cursor-pointer group"
                  >
                    <div className="flex items-center gap-3">
                      <Medal className="w-4 h-4 text-emerald-400" />
                      <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest group-hover:text-emerald-400 transition-colors">
                        {getFullCourseName(course)}
                      </h3>
                      <span className="text-[10px] text-theme-secondary font-bold">
                        {groupedByCourse[course].length} races
                      </span>
                    </div>
                    <div className="p-1 rounded-lg bg-white/5 border border-white/10 group-hover:bg-emerald-500/10 group-hover:border-emerald-500/20 transition-colors">
                      {expanded ? (
                        <ChevronUp className="w-3.5 h-3.5 text-emerald-400" />
                      ) : (
                        <ChevronDown className="w-3.5 h-3.5 text-slate-400 group-hover:text-emerald-400 transition-colors" />
                      )}
                    </div>
                  </button>

                  {/* Accordion Content */}
                  <AnimatePresence initial={false}>
                    {expanded && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: 'auto', opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
                        className="overflow-hidden space-y-3 mt-2 pl-2 border-l border-emerald-500/10"
                      >
                        {groupedByCourse[course].map((race, idx) => (
                          <RaceCard key={`${race.course}-${race.time}-${idx}`} race={race} />
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Footer */}
      {results.length > 0 && (
        <div className="shrink-0 pt-3 border-t border-theme">
          <p className="text-[10px] text-theme-secondary font-semibold">
            Results sourced from ATR — updated every 30s
          </p>
        </div>
      )}
    </motion.div>
  );
};
