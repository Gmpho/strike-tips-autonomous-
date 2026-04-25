import * as React from 'react';
import { useEffect, useState } from 'react';
import { useHUD } from './hooks/useHUD';
import { AgentDashboard } from './components/AgentDashboard';
import { RaceCard } from './components/RaceCard.tsx';
import { Shield, Cpu, Zap } from 'lucide-react';
import type { RaceEvent } from './types';
import { Sidebar } from './components/sidebar/Sidebar.tsx';
import { BankrollView } from './components/sidebar/BankrollView';
import { LogsView } from './components/sidebar/LogsView';
import { SettingsView } from './components/sidebar/SettingsView';
import { AnalyticsView } from './components/sidebar/AnalyticsView';
import { HealingView } from './components/sidebar/HealingView';
import { SystemVitalsView } from './components/sidebar/SystemVitalsView';
import { ThemeToggle } from './components/ThemeToggle';
import { AmbientCanvas } from './components/visualizer/AmbientCanvas';
import { motion, AnimatePresence } from 'framer-motion';


export const App: React.FC = () => {
  const [activeView, setActiveView] = useState('dashboard');
  const state = useHUD();

  // Load-sensing for background effects
  useEffect(() => {
    if (state.systemHealth.cpu > 60) {
      document.body.classList.add('low-power');
    } else {
      document.body.classList.remove('low-power');
    }
  }, [state.systemHealth.cpu]);

  const renderView = () => {
    // Instant Load Logic: Only show spinner if we have NO data AND no cached events from localStorage
    const hasCachedData = Object.keys(state.events).length > 0 || (state.bankroll && state.bankroll.balance > 0);

    if (!hasCachedData && activeView === 'dashboard') {
      return (
        <div key="loading-state" className="flex-1 flex flex-col items-center justify-center p-12 h-full">
          <div className="w-16 h-16 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin mb-4" />
          <p className="text-slate-500 font-black uppercase tracking-widest animate-pulse">Initializing Neural Link...</p>
        </div>
      );
    }

    switch (activeView) {
      case 'dashboard':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 flex-1 z-10">
            {Object.values(state.events).map(event => (
              <RaceCard key={event.id} event={event as RaceEvent} />
            ))}
          </div>
        );
      case 'agents':
        return <AgentDashboard key="agents-view" />;
      case 'bankroll':
        return <BankrollView key="bankroll-view" />;
      case 'analytics':
        return <AnalyticsView key="analytics-view" />;
      case 'logs':
        return <LogsView key="logs-view" />;
      case 'settings':
        return <SettingsView key="settings-view" />;
      case 'healing':
        return <HealingView key="healing-view" />;
      case 'vitals':
        return <SystemVitalsView key="vitals-view" />;
      default:
        return <div key="default-view" className="text-white p-12">Select a module</div>;
    }
  };

  const isOnline = state.systemHealth.status === 'ONLINE';

  return (
    <div className="flex h-screen bg-black text-white selection:bg-purple-500/30 overflow-hidden">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      
      <div className="flex-1 relative overflow-auto p-8 lg:p-12">
        {/* Ambient Background Layer (React Three Fiber) */}
        <AmbientCanvas />

        {/* UI Overlay */}
        <div className="relative z-10 flex flex-col h-full pointer-events-none">
          <header className="flex justify-between items-center mb-10 pointer-events-auto">
            <div className="flex flex-col">
              <h1 className="text-gradient text-4xl font-black tracking-tighter mb-1">STRIKE TIPS</h1>
              <div className="flex items-center gap-2.5">
                <span className={`w-2 h-2 rounded-full shadow-[0_0_10px] transition-colors duration-500 ${
                  isOnline ? 'bg-emerald-500 shadow-emerald-500' : 'bg-amber-500 shadow-amber-500'
                }`} />
                <span className="text-[11px] font-black text-slate-500 uppercase tracking-[0.2em]">
                  {isOnline ? 'L7 GHOST SYNC ACTIVE' : 'LOCAL INTELLIGENCE CACHE'}
                </span>
              </div>
            </div>
            
            <div className="flex items-center gap-8">
              <div className="hidden md:flex items-center gap-4 text-right">
                <div className="flex flex-col">
                  <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">System Load</span>
                  <span className="text-xs font-mono font-bold text-purple-400 flex items-center gap-1.5 justify-end">
                    <Cpu className="w-3 h-3" /> {state.systemHealth.cpu}%
                  </span>
                </div>
                <div className="h-10 w-px bg-white/10" />
                <div className="flex flex-col">
                  <span className="text-[9px] font-black text-slate-600 uppercase tracking-widest">Active Edge</span>
                  <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1.5 justify-end">
                    <Zap className="w-3 h-3 fill-emerald-400" /> {state.learning?.totalRoi.toFixed(1) || '0.0'}% ROI
                  </span>
                </div>
              </div>

              <div className="bg-white/5 border border-white/10 px-5 py-3 rounded-2xl backdrop-blur-2xl flex items-center gap-4">
                <div>
                  <div className="text-[9px] font-black text-slate-500 uppercase mb-0.5 tracking-tighter">Active Capital</div>
                  <div className="text-sm font-mono font-black text-white">R {state.bankroll?.balance.toLocaleString() || '0.00'}</div>
                </div>
                <Shield className="w-5 h-5 text-purple-500/50" />
                <ThemeToggle />
              </div>
            </div>
          </header>

          <AnimatePresence mode="popLayout">
            <motion.div 
              key={activeView}
              initial={{ opacity: 0, x: 10, filter: 'blur(10px)' }}
              animate={{ opacity: 1, x: 0, filter: 'blur(0px)' }}
              exit={{ opacity: 0, x: -10, filter: 'blur(10px)' }}
              transition={{ duration: 0.3, ease: "easeOut" }}
              className="flex-1 pointer-events-auto min-h-0"
            >
              {renderView()}
            </motion.div>
          </AnimatePresence>

          <footer className="mt-8 flex justify-between items-end border-t border-white/5 pt-6 pointer-events-auto">
            <div className="flex items-center gap-16">
              <div>
                <div className="text-[9px] font-black text-slate-600 uppercase mb-1.5 tracking-widest text-glow-sm">Total Exposure</div>
                <div className="text-base font-mono font-black tracking-tighter text-white/90">
                  R {(state.bankroll?.totalExposure || 0).toFixed(2)}
                </div>
              </div>
            </div>
            <div className="text-[10px] font-black text-slate-700 uppercase tracking-[0.3em]">
              &copy; 2026 STRIKE
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
};
