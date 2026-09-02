import React, { useMemo, useState } from 'react';
import type { RaceEvent, Runner } from '../types';
import { 
  Zap, Activity, Timer, ChevronDown, ChevronUp, ChevronUp as SortAsc, 
  ChevronDown as SortDesc, Flame, Star, CircleDot, Globe, LayoutList, Table as TableIcon 
} from 'lucide-react';
import { motion } from 'framer-motion';

interface RaceCardProps {
  event: RaceEvent;
  idx?: number;
  onExecutePosition?: (event: RaceEvent) => void;
  onExecuteRunner?: (event: RaceEvent, runner: Runner) => void;
}

type SortKey = 'name' | 'age' | 'draw' | 'starRating' | 'form' | 'edge' | 'odds' | 'daysSinceRun';

interface SortState {
  key: SortKey;
  dir: 1 | -1;
}

const COLUMNS = 12;

function isMissingForSort(r: Runner, key: SortKey): boolean {
  if (key === 'daysSinceRun') return typeof r.daysSinceRun !== 'number';
  return false;
}

function sortValue(r: Runner, key: SortKey): number | string {
  switch (key) {
    case 'name':
      return (r.name || '').toLowerCase();
    case 'age': {
      const m = String(r.age || '').match(/\d+/);
      return m ? parseInt(m[0], 10) : 999;
    }
    case 'draw':
      return typeof r.draw === 'number' ? r.draw : 999;
    case 'starRating':
      return r.starRating || 0;
    case 'form':
      return r.form || '';
    case 'edge':
      return typeof r.edge === 'number' ? r.edge : -999;
    case 'odds': {
      const o = typeof r.odds === 'number' ? r.odds : parseFloat(String(r.odds)) || 0;
      return o > 0 ? o : 99999;
    }
    case 'daysSinceRun':
      // Absent/unknown sorts last regardless of direction (sentinel via +Infinity)
      return typeof r.daysSinceRun === 'number' ? r.daysSinceRun : Number.POSITIVE_INFINITY;
  }
}

function InsightBanner({ text, kind }: { text: string; kind: 'timeform' | 'swarm' }) {
  const isTimeform = kind === 'timeform';
  return (
    <div
      className={`flex items-start gap-2 px-3 py-2 rounded-xl border ${
        isTimeform
          ? 'bg-amber-500/5 border-amber-500/15'
          : 'bg-cyan-500/5 border-cyan-500/15'
      }`}
    >
      {isTimeform ? (
        <Flame className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
      ) : (
        <Globe className="w-3.5 h-3.5 text-cyan-400 shrink-0 mt-0.5" />
      )}
      <div className="min-w-0">
        <p className={`text-[8px] font-black uppercase tracking-widest mb-0.5 ${isTimeform ? 'text-amber-400/70' : 'text-cyan-400/70'}`}>
          {isTimeform ? 'Timeform Comment' : 'Swarm Insight'}
        </p>
        <p className="text-xs font-medium text-slate-300 leading-snug">{text}</p>
      </div>
    </div>
  );
}

export const RaceCard: React.FC<RaceCardProps> = React.memo(({ event, onExecutePosition, onExecuteRunner }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<'value' | 'favourite' | 'outsider'>('value');
  const [sort, setSort] = useState<SortState | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');

  const topHorse = event.runners?.[0];
  const hasMarketData = topHorse && typeof topHorse.odds === 'number' && topHorse.odds > 0;

  // Resolve runner based on selectedCategory
  const selections = event.aiSelections || {};
  const selectedRunner = selections[selectedCategory] || topHorse;

  const toggleSort = (key: SortKey) => {
    setSort((prev) => {
      if (!prev || prev.key !== key) return { key, dir: 1 };
      if (prev.dir === 1) return { key, dir: -1 };
      return null;
    });
  };

  const sortedRunners = useMemo(() => {
    const runners = [...(event.runners || [])];
    if (!sort) return runners;
    return runners.sort((a, b) => {
      // Absent values sort last regardless of direction (spec contract).
      const aMissing = isMissingForSort(a, sort.key);
      const bMissing = isMissingForSort(b, sort.key);
      if (aMissing && bMissing) return 0;
      if (aMissing) return 1;
      if (bMissing) return -1;
      const va = sortValue(a, sort.key);
      const vb = sortValue(b, sort.key);
      let cmp: number;
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb;
      else cmp = String(va).localeCompare(String(vb));
      return cmp * sort.dir;
    });
  }, [event.runners, sort]);

  const SortHeader: React.FC<{ label: React.ReactNode; sortKey: SortKey; className?: string; title?: string }> = ({ label, sortKey, className = '', title }) => {
    const active = sort?.key === sortKey;
    return (
      <th className={`py-2.5 sm:py-3 px-2 cursor-pointer select-none hover:text-theme-primary transition-colors ${active ? 'text-purple-400' : ''} ${className}`}>
        <button
          onClick={(e) => { e.stopPropagation(); toggleSort(sortKey); }}
          className="inline-flex items-center gap-0.5 uppercase font-black text-[10px] sm:text-[11px]"
          aria-label={`Sort by ${sortKey}`}
          title={title}
        >
          {label}
          {active ? (
            sort?.dir === 1 ? <SortAsc className="w-2.5 h-2.5" /> : <SortDesc className="w-2.5 h-2.5" />
          ) : (
            <ChevronDown className="w-2.5 h-2.5 opacity-30" />
          )}
        </button>
      </th>
    );
  };

  return (
    <motion.div
      key={event.id}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.15 }}
      className={`hud-card group p-4 sm:p-6 relative overflow-hidden border border-theme bg-theme-panel transition-all hover:shadow-[0_0_30px_rgba(168,85,247,0.15)] rounded-2xl sm:rounded-3xl w-full min-w-0 ${
        isOpen ? 'col-span-1 md:col-span-2 xl:col-span-3' : ''
      }`}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex justify-between items-start mb-4 sm:mb-6 cursor-pointer text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/50 rounded-lg gap-2"
      >
        <div className="min-w-0 flex-1 pr-2">
          <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mb-1">
            <Activity className="w-3 h-3 text-purple-500 animate-pulse shrink-0" />
            <span className="text-[9px] sm:text-[10px] font-black text-purple-400 uppercase tracking-wider truncate">
              {event.course} · RACE {event.raceNumber || '---'}
            </span>
            {typeof event.dsi === 'number' && event.dsi > 0 && (
              <span className={`px-1.5 py-0.2 text-[7px] sm:text-[8px] font-black rounded border uppercase shrink-0 ${
                event.dsi < 0.2
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                  : event.dsi <= 0.5
                    ? 'bg-amber-500/10 text-amber-400 border-amber-500/30'
                    : 'bg-red-500/10 text-red-400 border-red-500/30'
              }`}>
                DSI {Math.round(event.dsi * 100)}%
              </span>
            )}
          </div>
          <h2 className="text-xl sm:text-2xl font-black text-theme-primary tracking-tight uppercase truncate">
            {event.course} R{event.raceNumber}
          </h2>
        </div>
        <div className="flex items-center gap-2 sm:gap-4 shrink-0">
          <div className="text-right">
            <div className="text-[8px] sm:text-[9px] font-bold text-theme-secondary mb-0.5">STATUS</div>
            <div className={`border ${hasMarketData ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10' : 'border-purple-500/40 text-purple-400 bg-purple-500/10'} text-[9px] sm:text-[10px] font-black px-1.5 sm:px-2 py-0.5 rounded uppercase`}>
              {hasMarketData ? 'LIVE MARKET' : 'EVALUATING'}
            </div>
          </div>
          <div className="p-1 rounded-lg bg-white/5 border border-white/5">
            {isOpen ? <ChevronUp className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" /> : <ChevronDown className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />}
          </div>
        </div>
      </button>

      {!isOpen ? (
        <div className="bg-theme-panel rounded-xl sm:rounded-2xl p-3.5 sm:p-5 border border-theme group-hover:border-purple-500/20 transition-colors">
          {/* Selections Toggles */}
          <div className="flex gap-1 sm:gap-1.5 border-b border-theme/30 pb-3 sm:pb-4 mb-3 sm:mb-4">
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('value'); }}
              className={`flex-1 py-1.5 px-1.5 rounded-lg text-[8px] sm:text-[9px] font-black uppercase tracking-normal border cursor-pointer transition-all flex items-center justify-center gap-1 sm:gap-1.5 min-h-[36px] ${
                selectedCategory === 'value'
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/30 shadow-xs'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Zap className="w-2.5 h-2.5 shrink-0" />
              <span className="truncate">AI Value</span>
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('favourite'); }}
              className={`flex-1 py-1.5 px-1.5 rounded-lg text-[8px] sm:text-[9px] font-black uppercase tracking-normal border cursor-pointer transition-all flex items-center justify-center gap-1 sm:gap-1.5 min-h-[36px] ${
                selectedCategory === 'favourite'
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/30 shadow-xs'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Star className="w-2.5 h-2.5 fill-current shrink-0" />
              <span className="truncate">Favourite</span>
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('outsider'); }}
              className={`flex-1 py-1.5 px-1.5 rounded-lg text-[8px] sm:text-[9px] font-black uppercase tracking-normal border cursor-pointer transition-all flex items-center justify-center gap-1 sm:gap-1.5 min-h-[36px] ${
                selectedCategory === 'outsider'
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30 shadow-xs'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Flame className="w-2.5 h-2.5 shrink-0" />
              <span className="truncate">Outsider</span>
            </button>
          </div>

          <div className="flex justify-between items-center gap-2">
            {selectedRunner ? (
              <>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5 mb-1">
                    <Zap className="w-3 h-3 text-purple-500 fill-purple-500 shrink-0" />
                    <div className="text-[8px] sm:text-[9px] font-extrabold text-purple-500 uppercase tracking-wider sm:tracking-widest truncate">
                      {selectedCategory === 'value' ? 'AI BEST VALUE' : selectedCategory === 'favourite' ? 'MARKET LEADER' : 'AI SHOUT-OUTSIDER'}
                    </div>
                  </div>
                  <div className="text-lg sm:text-xl font-black text-theme-primary tracking-tight leading-none mb-1.5 truncate">
                    {selectedRunner.name}
                  </div>
                  <div className="text-[9px] sm:text-[10px] text-theme-secondary font-bold">
                    {selectedRunner.edge !== undefined && selectedRunner.edge > 0 ? (
                      <span>EDGE: <span className="text-emerald-400 font-mono">+{selectedRunner.edge.toFixed(1)}%</span></span>
                    ) : (
                      <span>FORM: <span className="text-purple-400 font-mono">{selectedRunner.form || 'N/A'}</span></span>
                    )}
                  </div>
                  {(selectedRunner.draw !== undefined || selectedRunner.age || selectedRunner.weight || (selectedRunner.starRating && selectedRunner.starRating > 0)) && (
                    <div className="flex flex-wrap items-center gap-1.5 sm:gap-2 mt-1.5 text-[9px] sm:text-[10px] font-bold text-theme-secondary">
                      {typeof selectedRunner.draw === 'number' && (
                        <span className="border border-theme rounded px-1">D{selectedRunner.draw}</span>
                      )}
                      {selectedRunner.age && <span>{String(selectedRunner.age).replace(' years', 'yo')}</span>}
                      {selectedRunner.weight && <span>{selectedRunner.weight}</span>}
                      {selectedRunner.starRating ? (
                        <span className="flex items-center gap-0.5 text-amber-400">
                          {Array.from({ length: Math.min(selectedRunner.starRating, 5) }).map((_, si) => (
                            <Star key={si} className="w-2.5 h-2.5 fill-amber-400" />
                          ))}
                        </span>
                      ) : null}
                    </div>
                  )}
                </div>
                <div className="text-right shrink-0">
                  <div className="tabular text-2xl sm:text-3xl font-black text-theme-primary leading-none">
                    {typeof selectedRunner.odds === 'number' && selectedRunner.odds > 0 ? selectedRunner.odds.toFixed(2) : selectedRunner.odds || 'SP'}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-theme-secondary text-xs sm:text-sm font-bold uppercase tracking-widest w-full text-center py-2">No selection found</div>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4 space-y-3 animate-in fade-in slide-in-from-top-4 duration-300">
          {/* Header Controls for Expanded View: View switcher on small screens */}
          <div className="flex items-center justify-between gap-2 pb-1">
            <div className="flex items-center gap-1 text-[10px] text-theme-secondary font-black uppercase tracking-wider">
              <span className="text-purple-400">{sortedRunners.length}</span> Runners
            </div>

            {/* Mobile View Toggle: Table vs Cards */}
            <div className="flex sm:hidden items-center bg-theme-secondary border border-theme rounded-xl p-0.5">
              <button
                type="button"
                onClick={() => setViewMode('table')}
                className={`p-1.5 rounded-lg text-[9px] font-black uppercase flex items-center gap-1 transition-all ${
                  viewMode === 'table' ? 'bg-purple-500/20 text-purple-300' : 'text-theme-secondary'
                }`}
                aria-label="Table view"
              >
                <TableIcon className="w-3 h-3" />
                Table
              </button>
              <button
                type="button"
                onClick={() => setViewMode('cards')}
                className={`p-1.5 rounded-lg text-[9px] font-black uppercase flex items-center gap-1 transition-all ${
                  viewMode === 'cards' ? 'bg-purple-500/20 text-purple-300' : 'text-theme-secondary'
                }`}
                aria-label="Cards view"
              >
                <LayoutList className="w-3 h-3" />
                Cards
              </button>
            </div>
          </div>

          {/* 1. Mobile Cards Layout (No Horizontal Scroll Required) */}
          {viewMode === 'cards' ? (
            <div className="sm:hidden space-y-2.5">
              {sortedRunners.map((r) => {
                const insightText = r.timeForm || r.swarmInsight || '';
                const insightKind: 'timeform' | 'swarm' = r.timeForm ? 'timeform' : 'swarm';
                const isExpanded = expandedRow === r.name;
                const hasInsight = Boolean(insightText);
                const hasEnriched = Boolean(r.gear || typeof r.daysSinceRun === 'number' || r.runner_comments || r.official_rating || r.pedigree || r.owner || r.verdict || r.jockey_claim);
                const hasExpandable = hasInsight || hasEnriched;
                const edgeVal = typeof r.edge === 'number' ? r.edge : null;

                return (
                  <div 
                    key={r.name}
                    className={`p-3 rounded-2xl border transition-all ${
                      isExpanded ? 'bg-purple-500/10 border-purple-500/30' : 'bg-theme-secondary/40 border-theme hover:border-purple-500/20'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-1.5 mb-1">
                          {typeof r.draw === 'number' && (
                            <span className="px-1.5 py-0.5 text-[8px] font-black rounded bg-white/5 border border-theme text-theme-secondary">
                              D{r.draw}
                            </span>
                          )}
                          <span className="font-black text-sm text-theme-primary leading-tight truncate">{r.name}</span>
                          {r.region && (
                            <span className="px-1 py-0.2 text-[7px] font-black rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 uppercase shrink-0">
                              {r.region}
                            </span>
                          )}
                        </div>
                        <div className="text-[10px] text-theme-secondary truncate">
                          {r.jockeyName || 'TBA'} / {r.trainerName || 'TBA'}
                        </div>
                        <div className="flex flex-wrap items-center gap-2 mt-1.5 text-[9px] font-bold text-theme-secondary">
                          {r.form && <span>Form: <strong className="text-purple-400 font-mono">{r.form}</strong></span>}
                          {edgeVal !== null && edgeVal > 0 && (
                            <span>Edge: <strong className="text-emerald-400 font-mono">+{edgeVal.toFixed(1)}%</strong></span>
                          )}
                          {typeof r.daysSinceRun === 'number' && (
                            <span>Days: <strong className="text-slate-300 font-mono">{r.daysSinceRun}d</strong></span>
                          )}
                          {r.gear && <span>Gear: <strong className="text-cyan-300">{r.gear}</strong></span>}
                        </div>
                        {(r.owner || r.pedigree) && (
                          <div className="flex flex-wrap items-center gap-2 mt-1 text-[8px] text-theme-secondary">
                            {r.owner && <span className="truncate max-w-[140px]">Owner: <strong className="text-slate-300">{r.owner}</strong></span>}
                            {r.pedigree && <span className="truncate max-w-[160px]">Ped: <strong className="text-slate-300">{r.pedigree}</strong></span>}
                          </div>
                        )}
                      </div>

                      <div className="flex flex-col items-end gap-2 shrink-0">
                        <div className="text-lg font-black text-purple-400 font-mono tabular">
                          {(typeof r.odds === 'number' && r.odds > 0) ? r.odds.toFixed(2) : (r.odds || 'SP')}
                        </div>
                        <div className="flex items-center gap-1.5">
                          {hasExpandable && (
                            <button
                              type="button"
                              onClick={() => setExpandedRow(isExpanded ? null : r.name)}
                              className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary"
                              aria-label="Toggle details"
                            >
                              {isExpanded ? <ChevronUp className="w-3.5 h-3.5 text-purple-400" /> : <ChevronDown className="w-3.5 h-3.5" />}
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={() => onExecuteRunner?.(event, r)}
                            disabled={!onExecuteRunner}
                            className="p-1.5 rounded-lg bg-purple-500/20 border border-purple-500/30 text-purple-300 hover:bg-purple-500 hover:text-white transition-all"
                            aria-label={`Analyze ${r.name}`}
                          >
                            <Zap className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {isExpanded && (
                      <div className="mt-3 pt-2.5 border-t border-theme/30 space-y-2">
                        {hasInsight && <InsightBanner text={insightText} kind={insightKind} />}
                        {hasEnriched && (
                          <div className="grid grid-cols-1 gap-1.5 text-[10px] bg-black/20 p-2.5 rounded-xl border border-white/5">
                            {r.gear && <div><span className="font-black text-cyan-400 uppercase text-[8px]">Gear:</span> <span className="text-cyan-300">{r.gear}</span></div>}
                            {typeof r.daysSinceRun === 'number' && <div><span className="font-black text-slate-400 uppercase text-[8px]">Days:</span> <span className="text-slate-300">{r.daysSinceRun} days</span></div>}
                            {r.runner_comments && <div><span className="font-black text-purple-400 uppercase text-[8px]">Comments:</span> <span className="text-slate-300">{r.runner_comments}</span></div>}
                            {r.verdict && <div><span className="font-black text-emerald-400 uppercase text-[8px]">Verdict:</span> <span className="text-slate-300">{r.verdict}</span></div>}
                            {r.official_rating !== undefined && <div><span className="font-black text-amber-400 uppercase text-[8px]">Rating:</span> <span className="text-slate-300">{r.official_rating}</span></div>}
                            {r.jockey_claim && <div><span className="font-black text-cyan-400 uppercase text-[8px]">Claim:</span> <span className="text-slate-300">{r.jockey_claim}</span></div>}
                            {r.pedigree && <div><span className="font-black text-slate-400 uppercase text-[8px]">Pedigree:</span> <span className="text-slate-300">{r.pedigree}</span></div>}
                            {r.owner && <div><span className="font-black text-slate-400 uppercase text-[8px]">Owner:</span> <span className="text-slate-300">{r.owner}</span></div>}
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          ) : (
            /* 2. Responsive Table View with Sticky Horse Name Column */
            <div className="relative touch-scroll-x custom-scrollbar rounded-2xl border border-theme/40 bg-theme-panel/50">
              <table className="w-full text-[11px] text-left border-collapse min-w-[720px]">
                <thead className="sticky top-0 bg-theme-secondary z-10">
                  <tr className="text-theme-secondary border-b border-theme uppercase font-black">
                    <SortHeader label="Horse" sortKey="name" className="sticky-col-header bg-theme-panel z-20 min-w-[140px] pl-3" />
                    <th className="py-2.5 sm:py-3 px-2 whitespace-nowrap">Jockey/Trainer</th>
                    <SortHeader label="Age" sortKey="age" />
                    <th className="py-2.5 sm:py-3 px-2">Wgt</th>
                    <SortHeader label="Draw" sortKey="draw" className="text-center" />
                    <SortHeader label={<Star className="w-3 h-3 inline" />} sortKey="starRating" className="text-center" />
                    <th className="py-2.5 sm:py-3 px-2">Gear</th>
                    <SortHeader label="Form" sortKey="form" />
                    <SortHeader label="Days" sortKey="daysSinceRun" className="text-center" title="Days since last run" />
                    <SortHeader label="Edge" sortKey="edge" className="text-right" />
                    <SortHeader label="Odds" sortKey="odds" className="text-right" />
                    <th className="py-2.5 sm:py-3 px-2 text-right pr-3"><Zap className="w-3 h-3 inline opacity-50" /></th>
                  </tr>
                </thead>
                <tbody className="text-theme-primary font-mono">
                  {sortedRunners.map((r) => {
                    const insightText = r.timeForm || r.swarmInsight || '';
                    const insightKind: 'timeform' | 'swarm' = r.timeForm ? 'timeform' : 'swarm';
                    const isExpanded = expandedRow === r.name;
                    const hasInsight = Boolean(insightText);
                    const hasEnriched = Boolean(r.gear || typeof r.daysSinceRun === 'number' || r.runner_comments || r.official_rating || r.pedigree || r.owner || r.verdict || r.jockey_claim);
                    const hasExpandable = hasInsight || hasEnriched;
                    const edgeVal = typeof r.edge === 'number' ? r.edge : null;

                    return (
                      <React.Fragment key={r.name}>
                        <tr className={`border-b border-theme hover:bg-purple-500/10 transition-colors ${isExpanded ? 'bg-purple-500/5' : ''}`}>
                          <td className="py-2.5 px-2 align-middle sticky-col-cell bg-theme-panel z-10 pl-3">
                            <button
                              onClick={() => hasExpandable && setExpandedRow(isExpanded ? null : r.name)}
                              disabled={!hasExpandable}
                              className={`flex items-center gap-1.5 text-left max-w-[160px] sm:max-w-none ${hasExpandable ? 'cursor-pointer group/row' : 'cursor-default'}`}
                              aria-expanded={isExpanded}
                              title={hasExpandable ? (isExpanded ? 'Hide details' : 'Show details') : undefined}
                            >
                              {hasExpandable && (isExpanded
                                ? <ChevronUp className="w-3 h-3 shrink-0 text-purple-400" />
                                : <ChevronDown className="w-3 h-3 shrink-0 text-slate-500 group-hover/row:text-purple-400 transition-colors" />)}
                              <span className="font-black text-xs sm:text-sm leading-tight truncate">{r.name}</span>
                              {r.region && (
                                <span className="px-1.5 py-0.2 text-[7px] sm:text-[8px] font-black rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 uppercase shrink-0">
                                  {r.region}
                                </span>
                              )}
                            </button>
                          </td>
                          <td className="py-2.5 px-2 text-[10px] opacity-80 whitespace-nowrap align-middle">{r.jockeyName || 'TBA'} / {r.trainerName || 'TBA'}</td>
                          <td className="py-2.5 px-2 font-bold whitespace-nowrap align-middle">{r.age ? String(r.age).replace(' years', 'yo') : '-'}</td>
                          <td className="py-2.5 px-2 whitespace-nowrap align-middle">{r.weight || '-'}</td>
                          <td className="py-2.5 px-2 text-center font-black align-middle">{typeof r.draw === 'number' ? r.draw : '-'}</td>
                          <td className="py-2.5 px-2 text-center text-amber-400 align-middle">
                            {r.starRating && r.starRating > 0 ? (
                              <span className="flex items-center justify-center gap-0.5">
                                {Array.from({ length: Math.min(r.starRating, 5) }).map((_, si) => (
                                  <Star key={si} className="w-2.5 h-2.5 fill-amber-400" />
                                ))}
                              </span>
                            ) : '-'}
                          </td>
                          <td className="py-2.5 px-2 align-middle" title={r.gear || 'No gear data'}>
                            {r.gear ? (
                              <div className="flex flex-wrap gap-1 items-center max-w-[120px]">
                                {r.gear.split(' · ').map((tok, ti) => (
                                  <span
                                    key={ti}
                                    className="px-1.5 py-0.5 text-[8px] font-black uppercase tracking-wide rounded border border-cyan-500/30 bg-cyan-500/10 text-cyan-300"
                                  >
                                    {tok}
                                  </span>
                                ))}
                              </div>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-2 font-bold align-middle whitespace-nowrap">{r.form || '-'}</td>
                          <td className="py-2.5 px-2 text-center text-theme-secondary tabular-nums align-middle">
                            {typeof r.daysSinceRun === 'number' ? r.daysSinceRun : <span className="text-slate-600">—</span>}
                          </td>
                          <td className="py-2.5 px-2 text-right align-middle whitespace-nowrap">
                            {edgeVal !== null && edgeVal > 0 ? (
                              <span className="font-black text-emerald-400 tabular-nums" title={r.winProbability ? `Model win probability: ${(r.winProbability * 100).toFixed(1)}%` : undefined}>
                                +{edgeVal.toFixed(1)}%
                              </span>
                            ) : (
                              <span className="text-slate-600">—</span>
                            )}
                          </td>
                          <td className="py-2.5 px-2 text-right font-black text-purple-500 text-sm whitespace-nowrap align-middle">
                            {(typeof r.odds === 'number' && r.odds > 0) ? r.odds.toFixed(2) : (r.odds || 'SP')}
                          </td>
                          <td className="py-2.5 px-2 text-right align-middle pr-3">
                            <button
                              onClick={() => onExecuteRunner?.(event, r)}
                              disabled={!onExecuteRunner}
                              className="p-1.5 rounded-lg bg-white/5 border border-white/10 text-theme-secondary hover:bg-purple-500/10 hover:border-purple-500/30 hover:text-purple-300 transition-all active:scale-90 disabled:opacity-40"
                              aria-label={`Analyze ${r.name} with AI chat`}
                              title={`Analyze ${r.name}`}
                            >
                              <Zap className="w-3.5 h-3.5" />
                            </button>
                          </td>
                        </tr>
                        {isExpanded && hasInsight && (
                          <tr className="border-b border-theme">
                            <td colSpan={COLUMNS} className="py-2 px-3">
                              <InsightBanner text={insightText} kind={insightKind} />
                            </td>
                          </tr>
                        )}
                        {isExpanded && (r.gear || typeof r.daysSinceRun === 'number' || r.runner_comments || r.official_rating || r.pedigree || r.owner || r.verdict || r.jockey_claim) && (
                          <tr className="border-b border-theme">
                            <td colSpan={COLUMNS} className="py-2 px-3">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px]">
                                {r.gear && <div><span className="font-black text-cyan-400 uppercase text-[9px]">Gear:</span> <span className="text-cyan-300">{r.gear}</span></div>}
                                {typeof r.daysSinceRun === 'number' && <div><span className="font-black text-slate-400 uppercase text-[9px]">Days:</span> <span className="text-slate-300">{r.daysSinceRun} days</span></div>}
                                {r.runner_comments && <div><span className="font-black text-purple-400 uppercase text-[9px]">Comments:</span> <span className="text-slate-300">{r.runner_comments}</span></div>}
                                {r.verdict && <div><span className="font-black text-emerald-400 uppercase text-[9px]">Verdict:</span> <span className="text-slate-300">{r.verdict}</span></div>}
                                {r.official_rating !== undefined && <div><span className="font-black text-amber-400 uppercase text-[9px]">Rating:</span> <span className="text-slate-300">{r.official_rating}</span></div>}
                                {r.jockey_claim && <div><span className="font-black text-cyan-400 uppercase text-[9px]">Claim:</span> <span className="text-slate-300">{r.jockey_claim}</span></div>}
                                {r.pedigree && <div><span className="font-black text-slate-400 uppercase text-[9px]">Pedigree:</span> <span className="text-slate-300">{r.pedigree}</span></div>}
                                {r.owner && <div><span className="font-black text-slate-400 uppercase text-[9px]">Owner:</span> <span className="text-slate-300">{r.owner}</span></div>}
                              </div>
                            </td>
                          </tr>
                        )}
                      </React.Fragment>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      <div className="mt-4 sm:mt-6 flex flex-wrap justify-between items-center gap-3">
        <div className="flex items-center gap-2">
          <Timer className="w-3 h-3 text-theme-secondary shrink-0" />
          <span className="text-[9px] sm:text-[10px] text-theme-secondary font-black uppercase tracking-wider sm:tracking-widest">
            OFF_TIME: {event.t}
          </span>
        </div>
        <button
          onClick={() => onExecutePosition?.(event)}
          className="inline-flex items-center gap-1.5 bg-theme-primary text-theme-panel text-[10px] sm:text-[11px] font-black px-4 sm:px-5 py-2.5 rounded-xl uppercase tracking-tight
          hover:bg-purple-500 hover:text-white hover:shadow-[0_0_20px_rgba(168,85,247,0.3)] transition-all active:scale-95
          disabled:opacity-40 disabled:cursor-not-allowed min-h-[38px]"
          disabled={!onExecutePosition}
        >
          <CircleDot className="w-3.5 h-3.5 shrink-0" />
          Execute Position
        </button>
      </div>
    </motion.div>
  );
});
