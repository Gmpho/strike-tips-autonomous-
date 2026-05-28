import React from 'react';
import { Cpu, Zap, Shield, Search, Menu } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';
import { useHUD } from '../../hooks/useHUD';

interface HeaderProps {
  onToggleSidebar?: () => void;
  isSidebarCollapsed?: boolean;
}

export const Header: React.FC<HeaderProps> = ({ onToggleSidebar }) => {
  const state = useHUD();
  const isOnline = state.systemHealth.status === 'ONLINE';

  return (
    <header className="flex justify-between items-center pointer-events-auto">
      {/* Branding */}
      <div className="flex items-center gap-2 md:gap-6 min-w-0">
        <button
          onClick={onToggleSidebar}
          className="md:hidden p-2 rounded-xl bg-theme-secondary hover:bg-purple-500/10 text-theme-secondary hover:text-purple-500 transition-all border border-theme shrink-0"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="relative group shrink-0 hidden xs:flex">
          <div className="absolute -inset-2 bg-linear-to-r from-purple-600 to-emerald-600 rounded-2xl opacity-20 blur group-hover:opacity-40 transition-all duration-500" />
          <div className="relative bg-theme-panel border border-theme rounded-2xl p-1.5 md:p-2.5 backdrop-blur-xl">
             <div className="w-8 h-8 md:w-12 md:h-12 bg-purple-500/20 rounded-xl flex items-center justify-center overflow-hidden border border-purple-500/30">
               <img
                 src="/strike_tips_premium_logo.png"
                 alt="Strike Tips Logo"
                 className="w-full h-full object-cover"
               />
             </div>
          </div>
        </div>

        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5 md:gap-3">
            <h1 className="text-lg md:text-2xl lg:text-4xl font-black tracking-tighter bg-linear-to-r from-theme-primary via-theme-primary to-purple-500 bg-clip-text text-transparent truncate">
              STRIKE TIPS
            </h1>
            <div className="px-1.5 md:px-2 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded-md shrink-0">
              <span className="text-[7px] md:text-[9px] font-black text-purple-400 uppercase tracking-widest">v8.0 PRO</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 md:gap-2.5 mt-0.5 md:mt-1">
            <span className={`w-1.5 h-1.5 md:w-2 md:h-2 rounded-full shadow-[0_0_10px] transition-colors duration-500 ${
              isOnline ? 'bg-emerald-500 shadow-emerald-500' : 'bg-amber-500 shadow-amber-500'
            }`} />
            <span className="text-[8px] md:text-[11px] font-black text-theme-secondary opacity-70 uppercase tracking-[0.2em] truncate">
              {isOnline ? 'L7 GHOST SYNC ACTIVE' : 'LOCAL CACHE'}
            </span>
          </div>
        </div>
      </div>

      {/* Search & Vitals */}
      <div className="flex items-center gap-2 md:gap-4 lg:gap-8 shrink-0">
        <div className="relative hidden xl:flex items-center group">
          <Search className="absolute left-4 w-4 h-4 text-theme-secondary opacity-60 group-focus-within:text-purple-400 transition-colors" />
          <input
            type="text"
            placeholder="Search Intelligence..."
            className="bg-theme-secondary border border-theme rounded-2xl pl-12 pr-6 py-3.5 text-sm font-bold w-64 focus:outline-hidden focus:border-purple-500/50 focus:bg-purple-500/5 transition-all text-theme-primary"
          />
        </div>

        <div className="hidden sm:flex items-center gap-2 md:gap-4 text-right">
          <div className="flex flex-col">
            <span className="text-[8px] md:text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">CPU</span>
            <span className="text-[10px] md:text-xs font-mono font-bold text-purple-400 flex items-center gap-1 justify-end">
              <Cpu className="w-2.5 h-2.5 md:w-3 md:h-3" /> {state.systemHealth.cpu}%
            </span>
          </div>
          <div className="h-8 md:h-10 w-px bg-theme-secondary opacity-10" />
          <div className="flex flex-col">
            <span className="text-[8px] md:text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">Edge</span>
            <span className="text-[10px] md:text-xs font-mono font-bold text-emerald-400 flex items-center gap-1 justify-end">
              <Zap className="w-2.5 h-2.5 md:w-3 md:h-3 fill-emerald-400" /> {state.learning?.totalRoi.toFixed(1) || '0.0'}%
            </span>
          </div>
        </div>

        <div className="bg-theme-secondary border border-theme px-2 md:px-5 py-1.5 md:py-3 rounded-xl md:rounded-2xl backdrop-blur-2xl flex items-center gap-1.5 md:gap-4 hover:border-theme transition-all cursor-pointer group">
          <div className="hidden xs:block">
            <div className="text-[8px] md:text-[9px] font-black text-theme-secondary opacity-70 uppercase tracking-tighter">Capital</div>
            <div className="text-[11px] md:text-sm font-mono font-black text-theme-primary group-hover:text-purple-400 transition-colors">
              R {state.bankroll?.balance.toLocaleString() || '0'}
            </div>
          </div>
          <Shield className="w-4 h-4 md:w-5 md:h-5 text-purple-500/50 group-hover:text-purple-500 transition-colors" />
          <div className="h-5 md:h-6 w-px bg-theme-secondary opacity-10" />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
};
