import React from 'react';
import { 
  LayoutDashboard, BrainCircuit, Wallet, Settings, Terminal, 
  BarChart3, ShieldCheck, Activity, Sparkles, ChevronLeft, ChevronRight,
  TrendingUp, Flag, Ticket
} from 'lucide-react';
import { AgentStatus } from './AgentStatus';

interface SidebarProps {
  activeView: string;
  setActiveView: (view: string) => void;
  isCollapsed: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ 
  activeView, 
  setActiveView, 
  isCollapsed, 
  onToggle 
}) => {
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', id: 'dashboard' },
    { icon: BrainCircuit, label: 'AI Agents', id: 'agents' },
    { icon: Sparkles, label: 'Dreaming', id: 'dreaming' },
    { icon: Ticket, label: 'Exotics', id: 'exotics' },
    { icon: Wallet, label: 'Bankroll', id: 'bankroll' },
    { icon: BarChart3, label: 'Analytics', id: 'analytics' },
    { icon: Terminal, label: 'Logs', id: 'logs' },
    { icon: Settings, label: 'Settings', id: 'settings' },
  ];

  const adminItems = [
    { icon: ShieldCheck, label: 'Healing Cloud', id: 'healing' },
    { icon: Activity, label: 'System Vitals', id: 'vitals' },
  ];

  const racingItems = [
    { icon: TrendingUp, label: 'Market Movers', id: 'market-movers' },
    { icon: Sparkles, label: 'Predictor', id: 'predictor' },
    { icon: Flag, label: 'Results', id: 'results' },
  ];

  return (
    <nav className="h-full flex flex-col p-4">
      {/* Header & Toggle */}
      <div className="flex items-center justify-between mb-10 px-2">
        {!isCollapsed && (
          <h2 className="text-[10px] font-black text-purple-500 uppercase tracking-widest animate-in fade-in slide-in-from-left-2">
            Strike Control
          </h2>
        )}
        <button 
          onClick={onToggle}
          aria-label={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          className="p-1.5 rounded-lg bg-theme-secondary hover:bg-purple-500/10 text-theme-secondary hover:text-purple-500 transition-all border border-theme"
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
        </button>
      </div>

      <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto overflow-x-hidden custom-scrollbar">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            title={isCollapsed ? item.label : ""}
            className={`flex items-center gap-4 px-3 py-2.5 rounded-xl transition-all group shrink-0 ${
              activeView === item.id 
                ? 'text-theme-primary bg-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.2)] border border-purple-500/30' 
                : 'text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary'
            } ${isCollapsed ? 'justify-center px-0' : ''}`}
          >
            <item.icon className={`w-5 h-5 transition-colors ${activeView === item.id ? 'text-purple-400' : 'group-hover:text-purple-500'}`} />
            {!isCollapsed && (
              <span className="text-sm font-bold tracking-wide animate-in fade-in slide-in-from-left-1">
                {item.label}
              </span>
            )}
          </button>
        ))}

        <div className={`mt-6 mb-2 px-3 shrink-0 ${isCollapsed ? 'flex justify-center' : ''}`}>
          {!isCollapsed ? (
            <h2 className="text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">Racing Intelligence</h2>
          ) : (
            <div className="w-4 h-px bg-theme-secondary opacity-20" />
          )}
        </div>

        {racingItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            title={isCollapsed ? item.label : ""}
            className={`flex items-center gap-4 px-3 py-2.5 rounded-xl transition-all group shrink-0 ${
              activeView === item.id 
                ? 'text-theme-primary bg-amber-500/20 shadow-[0_0_15px_rgba(245,158,11,0.1)] border border-amber-500/30' 
                : 'text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary'
            } ${isCollapsed ? 'justify-center px-0' : ''}`}
          >
            <item.icon className={`w-5 h-5 transition-colors ${activeView === item.id ? 'text-amber-400' : 'group-hover:text-amber-500'}`} />
            {!isCollapsed && (
              <span className="text-sm font-bold tracking-wide animate-in fade-in slide-in-from-left-1">
                {item.label}
              </span>
            )}
          </button>
        ))}

        <div className={`mt-6 mb-2 px-3 shrink-0 ${isCollapsed ? 'flex justify-center' : ''}`}>
          {!isCollapsed ? (
            <h2 className="text-[9px] font-black text-theme-secondary opacity-50 uppercase tracking-widest">Admin</h2>
          ) : (
            <div className="w-4 h-px bg-theme-secondary opacity-20" />
          )}
        </div>

        {adminItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            title={isCollapsed ? item.label : ""}
            className={`flex items-center gap-4 px-3 py-2.5 rounded-xl transition-all group shrink-0 ${
              activeView === item.id 
                ? 'text-theme-primary bg-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)] border border-emerald-500/30' 
                : 'text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary'
            } ${isCollapsed ? 'justify-center px-0' : ''}`}
          >
            <item.icon className={`w-5 h-5 transition-colors ${activeView === item.id ? 'text-emerald-400' : 'group-hover:text-emerald-500'}`} />
            {!isCollapsed && (
              <span className="text-sm font-bold tracking-wide animate-in fade-in slide-in-from-left-1">
                {item.label}
              </span>
            )}
          </button>
        ))}
        
        {!isCollapsed && (
          <div className="mt-6 shrink-0 animate-in fade-in slide-in-from-bottom-2">
            <AgentStatus />
          </div>
        )}
      </div>

      <div className="mt-auto pt-4 border-t border-theme">
        <div className={`flex items-center gap-3 ${isCollapsed ? 'justify-center' : 'px-1'}`}>
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-500 font-black text-xs shrink-0">
            GT
          </div>
          {!isCollapsed && (
            <div className="flex flex-col animate-in fade-in slide-in-from-left-2">
              <span className="text-xs font-bold text-theme-primary truncate w-32">System Admin</span>
              <span className="text-[9px] text-theme-secondary opacity-70 uppercase">Operational</span>
            </div>
          )}
        </div>
      </div>
    </nav>
  );
};

