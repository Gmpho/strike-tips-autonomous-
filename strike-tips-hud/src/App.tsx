import * as React from 'react';
import { useEffect, useRef, useState } from 'react';
import { useHUD } from './hooks/useHUD';
import { AgentDashboard } from './components/AgentDashboard';
import { RaceCard } from './components/RaceCard.tsx';
import { VisualEngine } from './engine/visual-engine';
import { dataBridge } from './engine/data-bridge';
import { Shield, Cpu, Zap } from 'lucide-react';
import type { RaceEvent } from './types';
import { Sidebar } from './components/sidebar/Sidebar.tsx';
import { BankrollView } from './components/sidebar/BankrollView';
import { LogsView } from './components/sidebar/LogsView';
import { ThemeToggle } from './components/ThemeToggle';

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState('dashboard');
  const state = useHUD();
  const visualEngineRef = useRef<VisualEngine | null>(null);

  // Mark DOM as hydrated after first paint
  useEffect(() => {
    document.body.classList.add('hydrated');
  }, []);

  // Init engine once, wire to bridge
  useEffect(() => {
    if (visualEngineRef.current) return;
    try {
      visualEngineRef.current = new VisualEngine('ambient-canvas-container');
      visualEngineRef.current.start();
      dataBridge.setEngine(visualEngineRef.current);
    } catch (e) {
      console.warn('HUD: WebGL fallback active');
    }
  }, []);

  // Push state changes into engine
  useEffect(() => {
    visualEngineRef.current?.updateData(state.events);
  }, [state.events]);

  const renderView = () => {
    switch (activeView) {
      case 'dashboard':
        return (
          <main className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-8 flex-1 animate-in fade-in zoom-in-95 duration-1000">
            {Object.values(state.events).map(event => (
              <RaceCard key={event.id} event={event as RaceEvent} />
            ))}
          </main>
        );
      case 'agents':
        return <AgentDashboard />;
      case 'bankroll':
        return <BankrollView />;
      case 'logs':
        return <LogsView />;
      default:
        return <div className="text-white p-12">Select a module</div>;
    }
  };

  const isOnline = state.systemHealth.status === 'ONLINE';

  return (
    <div className="flex h-screen bg-black text-white selection:bg-purple-500/30 overflow-hidden">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      <div className="flex-1 relative overflow-auto p-8 lg:p-12">
        {/* Ambient Background Layer */}
        <div id="ambient-canvas-container" className="absolute inset-0 pointer-events-none z-0 opacity-30" />

        {/* UI Overlay */}
        <div className="relative z-10 flex flex-col h-full">
          <header className="flex justify-between items-center mb-12 animate-in fade-in slide-in-from-top duration-700">
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

          {renderView()}

          <footer className="mt-12 flex justify-between items-end border-t border-white/5 pt-8 animate-in fade-in slide-in-from-bottom duration-700">

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
