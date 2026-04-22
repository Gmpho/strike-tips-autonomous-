import React, { useState } from 'react';
import type { RaceEvent } from '../types';
import { Zap, Activity, Timer, ChevronDown, ChevronUp } from 'lucide-react';

interface RaceCardProps {
  event: RaceEvent;
}

export const RaceCard: React.FC<RaceCardProps> = ({ event }) => {
  const [isOpen, setIsOpen] = useState(false);
  const topHorse = event.runners?.[0];
  const hasMarketData = topHorse && topHorse.odds > 0;
  
  return (
    <div className={`hud-card group p-6 relative overflow-hidden border border-purple-500/20 bg-white/2 backdrop-blur-3xl transition-all duration-500 ${isOpen ? 'col-span-1 md:col-span-2 xl:col-span-3' : ''}`}>
      <div className="absolute inset-0 bg-linear-to-br from-purple-500/10 to-transparent pointer-events-none" />
      
      <div className="flex justify-between items-start mb-6 cursor-pointer" onClick={() => setIsOpen(!isOpen)}>
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-3 h-3 text-purple-500 animate-pulse" />
            <span className="text-[10px] font-black text-purple-500 uppercase tracking-[0.3em]">
              {event.course} | RACE {event.raceNumber || '---'}
            </span>
          </div>
          <h3 className="text-2xl font-black text-white tracking-tighter uppercase">{event.en}</h3>
        </div>
        <div className="flex items-center gap-4">
          <div className="text-right">
            <div className="text-[9px] font-bold text-slate-500 mb-1">STATUS</div>
            <div className={`border ${hasMarketData ? 'border-emerald-500/40 text-emerald-400 bg-emerald-500/20' : 'border-purple-500/40 text-purple-400 bg-purple-500/20'} text-[10px] font-black px-2 py-0.5 rounded uppercase`}>
              {hasMarketData ? 'LIVE MARKET' : 'EVALUATING'}
            </div>
          </div>
          {isOpen ? <ChevronUp className="w-5 h-5 text-purple-500" /> : <ChevronDown className="w-5 h-5 text-purple-500" />}
        </div>
      </div>

      {!isOpen ? (
        <div className="bg-void/50 rounded-2xl p-5 border border-white/5 group-hover:border-purple-500/20 transition-colors">
          <div className="flex justify-between items-center">
            {hasMarketData ? (
              <>
                <div>
                  <div className="flex items-center gap-1.5 mb-1">
                    <Zap className="w-3 h-3 text-purple-500 fill-purple-500" />
                    <div className="text-[9px] font-extrabold text-purple-500 uppercase tracking-widest">AI TOP SELECTION</div>
                  </div>
                  <div className="text-xl font-black text-white tracking-tight leading-none mb-1">{topHorse.name}</div>
                  <div className="text-[10px] text-slate-500 font-bold">FORM: <span className="text-purple-400">{topHorse.form || 'N/A'}</span></div>
                </div>
                <div className="text-right">
                  <div className="tabular text-3xl font-black text-white leading-none">{topHorse.odds.toFixed(2)}</div>
                </div>
              </>
            ) : (
              <div className="text-slate-500 text-sm font-bold uppercase tracking-widest">Awaiting Live Feed...</div>
            )}
          </div>
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto animate-in fade-in slide-in-from-top-4 duration-500">
          <table className="w-full text-[11px] text-left border-collapse">
            <thead>
              <tr className="text-slate-500 border-b border-white/10 uppercase font-black">
                <th className="py-3 px-2">Horse</th>
                <th className="py-3 px-2">Jockey/Trainer</th>
                <th className="py-3 px-2">Age/Wgt</th>
                <th className="py-3 px-2">Form</th>
                <th className="py-3 px-2 text-right">Odds</th>
              </tr>
            </thead>
            <tbody className="text-white font-mono">
            {event.runners.map((r, i) => (
              <tr key={i} className="border-b border-white/5 hover:bg-purple-500/10">
                <td className="py-3 px-2 font-bold">{r.name}</td>
                <td className="py-3 px-2">{r.jockeyName} / {r.trainerName}</td>
                <td className="py-3 px-2">{r.age} / {r.weight}</td>
                <td className="py-3 px-2">{r.form}</td>
                <td className="py-3 px-2 text-right font-black text-purple-400">
                  {r.odds > 0 ? (typeof r.odds === 'number' ? r.odds.toFixed(2) : r.odds) : 'SP'}
                </td>
              </tr>
            ))}
            </tbody>
            </table>
            </div>
            )}

            <div className="mt-6 flex justify-between items-center">
            <div className="flex items-center gap-2">
            <Timer className="w-3 h-3 text-slate-500" />
            <span className="text-[10px] text-slate-500 font-black uppercase tracking-widest">OFF_TIME: {event.t}</span>
            </div>
            <button className="bg-white text-black text-[11px] font-black px-5 py-2.5 rounded-xl cursor-pointer uppercase tracking-tighter 
            hover:bg-purple-500 hover:text-black hover:shadow-[0_0_20px_rgba(168,85,247,0.3)] transition-all active:scale-95">
            Execute Position
            </button>
            </div>
            </div>
            );
            };
