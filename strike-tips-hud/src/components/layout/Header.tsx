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
    <header className="flex justify-between items-center pointer-events-auto w-full gap-2">
      {/* Branding */}
      <div className="flex items-center gap-2 sm:gap-3 md:gap-6 min-w-0">
        <button
          onClick={onToggleSidebar}
          aria-label="Open navigation menu"
          className="md:hidden p-2 rounded-xl bg-theme-secondary hover:bg-purple-500/10 text-theme-secondary hover:text-purple-400 transition-all border border-theme shrink-0 active:scale-95"
        >
          <Menu className="w-5 h-5" />
        </button>

        <div className="relative group shrink-0 hidden sm:flex">
          <div className="absolute -inset-1.5 bg-linear-to-r from-purple-600 to-emerald-600 rounded-2xl opacity-20 blur group-hover:opacity-40 transition-all duration-500" />
          <div className="relative bg-theme-panel border border-theme rounded-2xl p-1.5 md:p-2.5">
             <div className="w-8 h-8 md:w-12 md:h-12 bg-purple-500/20 rounded-xl flex items-center justify-center overflow-hidden border border-purple-500/30">
               <picture>
                  <source srcSet="/logo.webp" type="image/webp" />
                  <img
                    src="/logo-128.png"
                    alt="Strike Tips Logo"
                    className="w-full h-full object-cover"
                    loading="lazy"
                  />
                </picture>
             </div>
          </div>
        </div>

        <div className="flex flex-col min-w-0">
          <div className="flex items-center gap-1.5 md:gap-3">
            <h1 className="text-base sm:text-xl md:text-2xl lg:text-4xl font-black tracking-tighter bg-linear-to-r from-theme-primary via-theme-primary to-purple-500 bg-clip-text text-transparent truncate">
              STRIKE TIPS
            </h1>
            <div className="px-1.5 py-0.5 bg-purple-500/10 border border-purple-500/20 rounded-md shrink-0">
              <span className="text-[7px] sm:text-[9px] font-black text-purple-400 uppercase tracking-widest">PRO</span>
            </div>
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`w-1.5 h-1.5 rounded-full shadow-[0_0_10px] shrink-0 transition-colors duration-500 ${
              isOnline ? 'bg-emerald-500 shadow-emerald-500' : 'bg-amber-500 shadow-amber-500'
            }`} />
            <span className="text-[8px] sm:text-[10px] md:text-[11px] font-black text-theme-secondary opacity-70 uppercase tracking-[0.15em] sm:tracking-[0.2em] truncate">
              {isOnline ? 'L7 GHOST SYNC' : 'LOCAL CACHE'}
            </span>
          </div>
        </div>
      </div>

      {/* Search & Vitals */}
      <div className="flex items-center gap-1.5 sm:gap-3 lg:gap-6 shrink-0">
        <div className="relative hidden xl:flex items-center group">
          <Search className="absolute left-4 w-4 h-4 text-theme-secondary opacity-60 group-focus-within:text-purple-400 transition-colors" />
          <input
            id="search-intelligence"
            name="search"
            type="text"
            placeholder="Search Intelligence..."
            aria-label="Search intelligence data"
            className="bg-theme-secondary border border-theme rounded-2xl pl-12 pr-6 py-3 text-sm font-bold w-60 focus:outline-hidden focus:border-purple-500/50 focus:bg-purple-500/5 transition-all text-theme-primary"
          />
        </div>

        <div className="hidden sm:flex items-center gap-2 md:gap-4 text-right">
          <div className="flex flex-col">
            <span className="text-[8px] md:text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">CPU</span>
            <span className="text-[10px] md:text-xs font-mono font-bold text-purple-400 flex items-center gap-1 justify-end">
              <Cpu className="w-2.5 h-2.5 md:w-3 md:h-3" /> {state.systemHealth.cpu}%
            </span>
          </div>
          <div className="h-7 md:h-9 w-px bg-theme-secondary opacity-10" />
          <div className="flex flex-col">
            <span className="text-[8px] md:text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">Edge</span>
            <span className="text-[10px] md:text-xs font-mono font-bold text-emerald-400 flex items-center gap-1 justify-end">
              <Zap className="w-2.5 h-2.5 md:w-3 md:h-3 fill-emerald-400" /> {state.learning?.totalRoi.toFixed(1) || '0.0'}%
            </span>
          </div>
        </div>

        <div className="bg-theme-secondary border border-theme px-2 sm:px-3.5 md:px-4 py-1.5 sm:py-2 rounded-xl sm:rounded-2xl flex items-center gap-1.5 sm:gap-3 hover:border-theme transition-all cursor-pointer group shrink-0">
          <div>
            <div className="text-[7px] sm:text-[8px] font-black text-theme-secondary opacity-70 uppercase tracking-tighter">Capital</div>
            <div className="text-[10px] sm:text-xs md:text-sm font-mono font-black text-theme-primary group-hover:text-purple-400 transition-colors">
              R {state.bankroll?.balance ? Math.round(state.bankroll.balance).toLocaleString() : '0'}
            </div>
          </div>
          <Shield className="w-3.5 h-3.5 sm:w-4 sm:h-4 text-purple-500/50 group-hover:text-purple-500 transition-colors hidden xs:block" />
          <div className="h-4 sm:h-5 w-px bg-theme-secondary opacity-10" />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
};
