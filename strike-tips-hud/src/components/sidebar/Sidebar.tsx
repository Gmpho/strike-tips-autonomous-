import React from 'react';
import { LayoutDashboard, BrainCircuit, Wallet, Settings, Terminal, BarChart3, ShieldCheck, Activity } from 'lucide-react';
import { AgentStatus } from './AgentStatus';

interface SidebarProps {
  activeView: string;
  setActiveView: (view: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeView, setActiveView }) => {
  const navItems = [
    { icon: LayoutDashboard, label: 'Dashboard', id: 'dashboard' },
    { icon: BrainCircuit, label: 'AI Agents', id: 'agents' },
    { icon: Wallet, label: 'Bankroll', id: 'bankroll' },
    { icon: BarChart3, label: 'Analytics', id: 'analytics' },
    { icon: Terminal, label: 'Logs', id: 'logs' },
    { icon: Settings, label: 'Settings', id: 'settings' },
  ];

  const adminItems = [
    { icon: ShieldCheck, label: 'Healing Cloud', id: 'healing' },
    { icon: Activity, label: 'System Vitals', id: 'vitals' },
  ];

  return (
    <nav className="w-64 h-full bg-black/40 border-r border-white/5 backdrop-blur-2xl flex flex-col p-6">
      <div className="mb-12">
        <h2 className="text-[10px] font-black text-purple-500 uppercase tracking-widest">Strike Control</h2>
      </div>

      <div className="flex flex-col gap-2 flex-1">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all group ${
              activeView === item.id 
                ? 'text-white bg-purple-500/20 shadow-[0_0_15px_rgba(168,85,247,0.2)] border border-purple-500/30' 
                : 'text-slate-500 hover:text-white hover:bg-white/5'
            }`}
          >
            <item.icon className={`w-5 h-5 transition-colors ${activeView === item.id ? 'text-purple-400' : 'group-hover:text-purple-500'}`} />
            <span className="text-sm font-bold tracking-wide">{item.label}</span>
          </button>
        ))}

        <div className="mt-4 mb-2 px-4">
          <h2 className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Admin Control</h2>
        </div>

        {adminItems.map((item) => (
          <button
            key={item.id}
            onClick={() => setActiveView(item.id)}
            className={`flex items-center gap-4 px-4 py-3 rounded-xl transition-all group ${
              activeView === item.id 
                ? 'text-white bg-emerald-500/20 shadow-[0_0_15px_rgba(16,185,129,0.1)] border border-emerald-500/30' 
                : 'text-slate-500 hover:text-white hover:bg-white/5'
            }`}
          >
            <item.icon className={`w-5 h-5 transition-colors ${activeView === item.id ? 'text-emerald-400' : 'group-hover:text-emerald-500'}`} />
            <span className="text-sm font-bold tracking-wide">{item.label}</span>
          </button>
        ))}
        
        <AgentStatus />
      </div>

      <div className="mt-auto pt-6 border-t border-white/5">
        <div className="flex items-center gap-3 px-2">
          <div className="w-8 h-8 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-500 font-black text-xs">
            GT
          </div>
          <div className="flex flex-col">
            <span className="text-xs font-bold text-white">System Admin</span>
            <span className="text-[9px] text-slate-600 uppercase">Operational</span>
          </div>
        </div>
      </div>
    </nav>
  );
};
