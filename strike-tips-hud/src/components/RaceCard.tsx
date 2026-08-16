import React, { useState } from 'react';
import type { RaceEvent } from '../types';
import { Zap, Activity, Timer, ChevronDown, ChevronUp } from 'lucide-react';
import { motion } from 'framer-motion';

interface RaceCardProps {
  event: RaceEvent;
  idx?: number;
  onExecutePosition?: (event: RaceEvent) => void;
}

export const RaceCard: React.FC<RaceCardProps> = React.memo(({ event, idx = 0, onExecutePosition }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedCategory, setSelectedCategory] = useState<'value' | 'favourite' | 'outsider'>('value');
  
  const topHorse = event.runners?.[0];
  const hasMarketData = topHorse && typeof topHorse.odds === 'number' && topHorse.odds > 0;
  
  // Resolve runner based on selectedCategory
  const selections = event.aiSelections || {};
  const selectedRunner = selections[selectedCategory] || selections['value'] || selections['favourite'] || selections['outsider'] || topHorse;
  
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
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all ${
                selectedCategory === 'value'
                  ? 'bg-purple-500/20 text-purple-300 border-purple-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              🎯 AI Value
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('favourite'); }}
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all ${
                selectedCategory === 'favourite'
                  ? 'bg-amber-500/20 text-amber-300 border-amber-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              ⭐ Favourite
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setSelectedCategory('outsider'); }}
              className={`flex-1 py-1.5 rounded-lg text-[9px] font-black uppercase tracking-wider border cursor-pointer transition-all ${
                selectedCategory === 'outsider'
                  ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/30'
                  : 'bg-transparent text-theme-secondary border-transparent hover:text-theme-primary'
              }`}
            >
              🔥 Outsider
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
            <thead className="sticky top-0 bg-theme-secondary">
              <tr className="text-theme-secondary border-b border-theme uppercase font-black">
                <th className="py-3 px-2">Horse</th>
                <th className="py-3 px-2">Jockey/Trainer</th>
                <th className="py-3 px-2">Form</th>
                <th className="py-3 px-2 text-right">Odds</th>
              </tr>
            </thead>
            <tbody className="text-theme-primary font-mono">
            {event.runners.map((r) => (
              <tr key={r.name} className="border-b border-theme hover:bg-purple-500/10 transition-colors">
                <td className="py-3 px-2 font-black text-sm">{r.name}</td>
                <td className="py-3 px-2 text-[10px] opacity-80">{r.jockeyName || 'TBA'} / {r.trainerName || 'TBA'}</td>
                <td className="py-3 px-2 font-bold">{r.form || '-'}</td>
                <td className="py-3 px-2 text-right font-black text-purple-500 text-sm">
                  {(typeof r.odds === 'number' && r.odds > 0) ? r.odds.toFixed(2) : (r.odds || 'SP')}
                </td>
              </tr>
            ))}
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
              className="bg-theme-primary text-theme-panel text-[11px] font-black px-5 py-2.5 rounded-xl uppercase tracking-tighter
              hover:bg-purple-500 hover:text-white hover:shadow-[0_0_20px_rgba(168,85,247,0.3)] transition-all active:scale-95
              disabled:opacity-40 disabled:cursor-not-allowed"
              disabled={!onExecutePosition}
            >
              ⚡ Execute Position
            </button>
            </div>
            </motion.div>
            );
            });
            
