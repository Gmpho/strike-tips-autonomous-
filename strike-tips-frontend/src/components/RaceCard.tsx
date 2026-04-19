import React, { memo } from 'react';
import { Sparkles, Loader2, ChevronDown, MapPin, Clock } from 'lucide-react';

interface RaceCardProps {
  race: any;
  isExpanded: boolean;
  isAnalyzing: boolean;
  analysis: any;
  onToggle: () => void;
  onAnalyze: (e: React.MouseEvent, track: string, raceNumber: number, raceId: string) => void;
}

export const RaceCard = memo(({ race, isExpanded, isAnalyzing, analysis, onToggle, onAnalyze }: RaceCardProps) => {
  return (
    <div 
      className={`glass-card rounded-[2rem] overflow-hidden transition-all duration-500 border border-white/5 ${isExpanded ? 'bg-white/5 ring-1 ring-amber-500/20 shadow-2xl shadow-amber-500/5' : 'hover:bg-white/10'}`}
    >
      <div 
        onClick={onToggle}
        className="p-5 flex items-center justify-between cursor-pointer group"
      >
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center border border-white/5 text-2xl font-black text-slate-700 group-hover:text-amber-500 transition-colors">
            R{race.raceNumber}
          </div>
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-bold text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-lg uppercase tracking-wider">
                {race.isFinished ? 'Settled' : 'Ready'}
              </span>
              <span className="text-xs text-slate-500 font-medium tracking-tight flex items-center gap-1.5">
                <MapPin className="w-3 h-3" /> {race.en} • <Clock className="w-3 h-3 ml-1" /> {race.t}
              </span>
            </div>
            <h4 className="text-lg font-bold text-white group-hover:translate-x-1 transition-transform">Market Analysis: {race.en}</h4>
          </div>
        </div>
        <div className="flex items-center gap-4">
            <div className="text-right mr-4 hidden sm:block">
              <p className="text-[10px] text-slate-500 font-bold uppercase mb-0.5">Status</p>
              <p className={`text-sm font-black ${race.isFinished ? 'text-slate-500' : 'text-emerald-500 animate-pulse'}`}>
                {race.isFinished ? 'Finished' : 'Live NOW'}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={(e) => onAnalyze(e, race.en, race.raceNumber, race.id)}
                disabled={isAnalyzing}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500 text-slate-900 font-bold text-sm shadow-lg shadow-amber-500/20 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:grayscale"
              >
                {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                {isAnalyzing ? 'Analyzing...' : 'Analyze'}
              </button>
              <div className={`p-2 rounded-xl bg-white/5 border border-white/10 transition-transform duration-500 ${isExpanded ? 'rotate-180' : ''}`}>
                <ChevronDown className="w-5 h-5 text-slate-400" />
              </div>
            </div>
        </div>
      </div>
      {/* Expanded Content omitted for brevity in memo example */}
    </div>
  );
});

RaceCard.displayName = 'RaceCard';
