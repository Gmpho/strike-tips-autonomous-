import React from 'react';
import { Cpu, Zap, Shield, Search } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';
import { useHUD } from '../../hooks/useHUD';

export const Header: React.FC = () => {
  const state = useHUD();
  const isOnline = state.systemHealth.status === 'ONLINE';

  return (
    <header className="flex justify-between items-center mb-10 pointer-events-auto">
      {/* Branding */}
      <div className="flex items-center gap-6">
        <div className="relative group">
          <div className="absolute -inset-2 bg-linear-to-r from-purple-600 to-emerald-600 rounded-2xl opacity-20 blur group-hover:opacity-40 transition-all duration-500" />
          <div className="relative bg-theme-panel border border-theme rounded-2xl p-2.5 backdrop-blur-xl">
             {/* Using the generated premium logo */}
             <div className="w-12 h-12 bg-purple-500/20 rounded-xl flex items-center justify-center overflow-hidden border border-purple-500/30">
               <img 
                 src="/strike_tips_premium_logo.png" 
                 alt="Strike Tips Logo" 
                 className="w-full h-full object-cover"
               />
             </div>
          </div>
        </div>

        <div className="flex flex-col">
          <div className="flex items-center gap-3">
            <h1 className="text-4xl font-black tracking-tighter bg-linear-to-r from-theme-primary via-theme-primary to-purple-500 bg-clip-text text-transparent">
              STRIKE TIPS
            </h1>
            <div className="px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded-md">
              <span className="text-[9px] font-black text-purple-400 uppercase tracking-widest">v8.0 PRO</span>
            </div>
          </div>
          <div className="flex items-center gap-2.5 mt-1">
            <span className={`w-2 h-2 rounded-full shadow-[0_0_10px] transition-colors duration-500 ${
              isOnline ? 'bg-emerald-500 shadow-emerald-500' : 'bg-amber-500 shadow-amber-500'
            }`} />
            <span className="text-[11px] font-black text-theme-secondary opacity-70 uppercase tracking-[0.2em]">
              {isOnline ? 'L7 GHOST SYNC ACTIVE' : 'LOCAL INTELLIGENCE CACHE'}
            </span>
          </div>
        </div>
      </div>
      
      {/* Search & Vitals */}
      <div className="flex items-center gap-8">
        <div className="relative hidden xl:flex items-center group">
          <Search className="absolute left-4 w-4 h-4 text-theme-secondary opacity-60 group-focus-within:text-purple-400 transition-colors" />
          <input 
            type="text" 
            placeholder="Search Intelligence..." 
            className="bg-theme-secondary border border-theme rounded-2xl pl-12 pr-6 py-3.5 text-sm font-bold w-64 focus:outline-hidden focus:border-purple-500/50 focus:bg-purple-500/5 transition-all text-theme-primary"
          />
        </div>

        <div className="hidden md:flex items-center gap-4 text-right">
          <div className="flex flex-col">
            <span className="text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">System Load</span>
            <span className="text-xs font-mono font-bold text-purple-400 flex items-center gap-1.5 justify-end">
              <Cpu className="w-3 h-3" /> {state.systemHealth.cpu}%
            </span>
          </div>
          <div className="h-10 w-px bg-theme-secondary opacity-10" />
          <div className="flex flex-col">
            <span className="text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">Active Edge</span>
            <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1.5 justify-end">
              <Zap className="w-3 h-3 fill-emerald-400" /> {state.learning?.totalRoi.toFixed(1) || '0.0'}% ROI
            </span>
          </div>
        </div>

        <div className="bg-theme-secondary border border-theme px-5 py-3 rounded-2xl backdrop-blur-2xl flex items-center gap-4 hover:border-theme transition-all cursor-pointer group">
          <div>
            <div className="text-[9px] font-black text-theme-secondary opacity-70 uppercase mb-0.5 tracking-tighter">Active Capital</div>
            <div className="text-sm font-mono font-black text-theme-primary group-hover:text-purple-400 transition-colors">
              R {state.bankroll?.balance.toLocaleString() || '0.00'}
            </div>
          </div>
          <Shield className="w-5 h-5 text-purple-500/50 group-hover:text-purple-500 transition-colors" />
          <div className="h-6 w-px bg-theme-secondary opacity-10" />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
};
