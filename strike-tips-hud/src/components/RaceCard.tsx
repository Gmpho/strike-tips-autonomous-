import React, { useMemo, useState } from 'react';
import type { RaceEvent, Runner } from '../types';
import { Zap, Activity, Timer, ChevronDown, ChevronUp, ChevronUp as SortAsc, ChevronDown as SortDesc, Flame, Star, CircleDot, Globe } from 'lucide-react';
import { motion } from 'framer-motion';

interface RaceCardProps {
  event: RaceEvent;
  idx?: number;
  onExecutePosition?: (event: RaceEvent) => void;
  onExecuteRunner?: (event: RaceEvent, runner: Runner) => void;
}

type SortKey = 'name' | 'age' | 'draw' | 'starRating' | 'form' | 'edge' | 'odds';

interface SortState {
  key: SortKey;
  dir: 1 | -1;
}

const COLUMNS = 10;

function sortValue(r: Runner, key: SortKey): number | string {
  switch (key) {
    case 'name':
      return (r.name || '').toLowerCase();
    case 'age': {
      const m = (r.age || '').match(/\d+/);
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

export const RaceCard: React.FC<RaceCardProps> = React.memo(({ event, idx = 0, onExecutePosition, onExecuteRunner }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<'value' | 'favourite' | 'outsider'>('value');
  const [sort, setSort] = useState<SortState | null>(null);
  const [expandedRow, setExpandedRow] = useState<string | null>(null);

  const topHorse = event.runners?.[0];
  const hasMarketData = topHorse && typeof topHorse.odds === 'number' && topHorse.odds > 0;

  // Resolve runner based on selectedCategory
  const selections = event.aiSelections || {};
  const selectedRunner = selections[selectedCategory] || selections['value'] || selections['favourite'] || selections['outsider'] || topHorse;

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
      const va = sortValue(a, sort.key);
      const vb = sortValue(b, sort.key);
      let cmp: number;
      if (typeof va === 'number' && typeof vb === 'number') cmp = va - vb;
      else cmp = String(va).localeCompare(String(vb));
      return cmp * sort.dir;
    });
  }, [event.runners, sort]);

  const SortHeader: React.FC<{ label: React.ReactNode; sortKey: SortKey; className?: string }> = ({ label, sortKey, className = '' }) => {
    const active = sort?.key === sortKey;
    return (
      <th className={`py-3 px-2 cursor-pointer select-none hover:text-theme-primary transition-colors ${active ? 'text-purple-400' : ''} ${className}`}>
        <button
          onClick={(e) => { e.stopPropagation(); toggleSort(sortKey); }}
          className="inline-flex items-center gap-0.5 uppercase font-black"
          aria-label={`Sort by ${sortKey}`}
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
      initial={{ x: -20, opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      transition={{ delay: Math.min(idx * 0.05, 0.4) }}
      className={`hud-card group p-6 relative overflow-hidden border border-theme bg-theme-panel transition-shadow hover:shadow-[0_0_30px_rgba(168,85,247,0.15)] rounded-3xl ${isOpen ? 'col-span-1 md:col-span-2 xl:col-span-3' : ''}`}
    >
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        className="w-full flex justify-between items-start mb-6 cursor-pointer text-left focus:outline-none focus-visible:ring-2 focus-visible:ring-purple-500/50 rounded-lg"
      >
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-3 h-3 text-purple-500 animate-pulse" />
            <span className="text-[10px] font-black text-purple-500 uppercase tracking-[0.3em]">
              {event.course} | RACE {event.raceNumber || '---'}
            </span>
            {typeof event.dsi === 'number' && event.dsi > 0 && (
              <span className={`px-1.5 py-0.5 text-[8px] font-black rounded border uppercase ${
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
          <h2 className="text-2xl font-black text-theme-primary tracking-tighter uppercase">{event.course} R{event.raceNumber}</h2>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[9px] font-bold text-theme-secondary mb-1">STATUS</div>
            <div className={`border ${hasMarketData ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/10' : 'border-purple-500/40 text-purple-400 bg-purple-500/10'} text-[10px] font-black px-2 py-0.5 rounded uppercase`}>
              {hasMarketData ? 'LIVE MARKET' : 'EVALUATING'}
            </div>
          </div>
          {isOpen ? <ChevronUp className="w-5 h-5 text-purple-500" /> : <ChevronDown className="w-5 h-5 text-purple-500" />}
        </div>
      </button>

      {!isOpen ? (
        <div className="bg-theme-panel rounded-2xl p-5 border border-theme group-hover:border-purple-500/20 transition-colors">
          {/* Selections Toggles */}
          <div className="flex gap-1.5 border-b border-theme/30 pb-4 mb-4">
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('value'); }}
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all flex items-center justify-center gap-1.5 ${
                selectedCategory === 'value'
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Zap className="w-2.5 h-2.5" />
              AI Value
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('favourite'); }}
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all flex items-center justify-center gap-1.5 ${
                selectedCategory === 'favourite'
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Star className="w-2.5 h-2.5 fill-current" />
              Favourite
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('outsider'); }}
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all flex items-center justify-center gap-1.5 ${
                selectedCategory === 'outsider'
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              <Flame className="w-2.5 h-2.5" />
              Outsider
            </button>
          </div>

          <div className="flex justify-between items-center">
            {selectedRunner ? (
              <>
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <Zap className="w-3 h-3 text-purple-500 fill-purple-500" />
                    <div className="text-[9px] font-extrabold text-purple-500 uppercase tracking-widest">
                      {selectedCategory === 'value' ? 'AI BEST VALUE' : selectedCategory === 'favourite' ? 'MARKET LEADER' : 'AI SHOUT-OUTSIDER'}
                    </div>
                  </div>
                  <div className="text-xl font-black text-theme-primary tracking-tight leading-none mb-1">{selectedRunner.name}</div>
                  <div className="text-[10px] text-theme-secondary font-bold">
                    {selectedRunner.edge !== undefined && selectedRunner.edge > 0 ? (
                      <span>EDGE: <span className="text-emerald-400">+{selectedRunner.edge.toFixed(1)}%</span></span>
                    ) : (
                      <span>FORM: <span className="text-purple-400">{selectedRunner.form || 'N/A'}</span></span>
                    )}
                  </div>
                  {(selectedRunner.draw !== undefined || selectedRunner.age || selectedRunner.weight || (selectedRunner.starRating && selectedRunner.starRating > 0)) && (
                    <div className="flex items-center gap-2 mt-1.5 text-[10px] font-bold text-theme-secondary">
                      {typeof selectedRunner.draw === 'number' && (
                        <span className="border border-theme rounded px-1">D{selectedRunner.draw}</span>
                      )}
                      {selectedRunner.age && <span>{selectedRunner.age.replace(' years', 'yo')}</span>}
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
                <div className="text-right">
                  <div className="tabular text-3xl font-black text-theme-primary leading-none">
                    {typeof selectedRunner.odds === 'number' && selectedRunner.odds > 0 ? selectedRunner.odds.toFixed(2) : selectedRunner.odds || 'SP'}
                  </div>
                </div>
              </>
            ) : (
              <div className="text-theme-secondary text-sm font-bold uppercase tracking-widest w-full text-center py-2">No selection found</div>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto animate-in fade-in slide-in-from-top-4 duration-500">
          <table className="w-full text-[11px] text-left border-collapse">
            <thead className="sticky top-0 bg-theme-secondary z-10">
              <tr className="text-theme-secondary border-b border-theme uppercase font-black">
                <SortHeader label="Horse" sortKey="name" />
                <th className="py-3 px-2">Jockey/Trainer</th>
                <SortHeader label="Age" sortKey="age" />
                <th className="py-3 px-2">Wgt</th>
                <SortHeader label="Draw" sortKey="draw" className="text-center" />
                <SortHeader label={<Star className="w-3 h-3 inline" />} sortKey="starRating" className="text-center" />
                <SortHeader label="Form" sortKey="form" />
                <SortHeader label="Edge" sortKey="edge" className="text-right" />
                <SortHeader label="Odds" sortKey="odds" className="text-right" />
                <th className="py-3 px-2 text-right"><Zap className="w-3 h-3 inline opacity-50" /></th>
              </tr>
            </thead>
            <tbody className="text-theme-primary font-mono">
            {sortedRunners.map((r) => {
              const insightText = r.timeForm || r.swarmInsight || '';
              const insightKind: 'timeform' | 'swarm' = r.timeForm ? 'timeform' : 'swarm';
              const isExpanded = expandedRow === r.name;
              const hasInsight = Boolean(insightText);
              const edgeVal = typeof r.edge === 'number' ? r.edge : null;
              return (
                <React.Fragment key={r.name}>
                  <tr className={`border-b border-theme hover:bg-purple-500/10 transition-colors ${isExpanded ? 'bg-purple-500/5' : ''}`}>
                    <td className="py-2.5 px-2 align-middle">
                      <button
                        onClick={() => hasInsight && setExpandedRow(isExpanded ? null : r.name)}
                        disabled={!hasInsight}
                        className={`flex items-center gap-1.5 text-left ${hasInsight ? 'cursor-pointer group/row' : 'cursor-default'}`}
                        aria-expanded={isExpanded}
                        title={hasInsight ? (isExpanded ? 'Hide insight' : 'Show insight') : undefined}
                      >
                        {hasInsight && (isExpanded
                          ? <ChevronUp className="w-3 h-3 shrink-0 text-purple-400" />
                          : <ChevronDown className="w-3 h-3 shrink-0 text-slate-500 group-hover/row:text-purple-400 transition-colors" />)}
                        <span className="font-black text-sm leading-tight whitespace-nowrap">{r.name}</span>
                        {r.region && (
                          <span className="px-1.5 py-0.5 text-[8px] font-black rounded bg-purple-500/20 text-purple-400 border border-purple-500/30 uppercase shrink-0">
                            {r.region}
                          </span>
                        )}
                      </button>
                    </td>
                    <td className="py-2.5 px-2 text-[10px] opacity-80 whitespace-nowrap align-middle">{r.jockeyName || 'TBA'} / {r.trainerName || 'TBA'}</td>
                    <td className="py-2.5 px-2 font-bold whitespace-nowrap align-middle">{r.age ? r.age.replace(' years', 'yo') : '-'}</td>
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
                    <td className="py-2.5 px-2 font-bold align-middle">{r.form || '-'}</td>
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
                    <td className="py-2.5 px-2 text-right align-middle">
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
                      <td colSpan={COLUMNS} className="py-2 px-2">
                        <InsightBanner text={insightText} kind={insightKind} />
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

            <div className="mt-6 flex justify-between items-center">
            <div className="flex items-center gap-2">
            <Timer className="w-3 h-3 text-theme-secondary" />
            <span className="text-[10px] text-theme-secondary font-black uppercase tracking-widest">OFF_TIME: {event.t}</span>
            </div>
            <button
              onClick={() => onExecutePosition?.(event)}
              className="inline-flex items-center gap-1.5 bg-theme-primary text-theme-panel text-[11px] font-black px-5 py-2.5 rounded-xl uppercase tracking-tighter
              hover:bg-purple-500 hover:text-white hover:shadow-[0_0_20px_rgba(168,85,247,0.3)] transition-all active:scale-95
              disabled:opacity-40 disabled:cursor-not-allowed"
              disabled={!onExecutePosition}
            >
              <CircleDot className="w-3.5 h-3.5" />
              Execute Position
            </button>
            </div>
            </motion.div>
            );
            });
