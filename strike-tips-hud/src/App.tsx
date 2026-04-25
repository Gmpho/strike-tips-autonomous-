import * as React from 'react';
import { useEffect, useState } from 'react';
import { useHUD } from './hooks/useHUD';
import { AgentDashboard } from './components/AgentDashboard';
import { RaceCard } from './components/RaceCard.tsx';
import type { RaceEvent } from './types';
import { Sidebar } from './components/sidebar/Sidebar.tsx';
import { BankrollView } from './components/sidebar/BankrollView';
import { LogsView } from './components/sidebar/LogsView';
import { SettingsView } from './components/sidebar/SettingsView';
import { AnalyticsView } from './components/sidebar/AnalyticsView';
import { HealingView } from './components/sidebar/HealingView';
import { SystemVitalsView } from './components/sidebar/SystemVitalsView';
import { DreamingView } from './components/sidebar/DreamingView';
import { AmbientCanvas } from './components/visualizer/AmbientCanvas';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
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
      case 'dreaming':
        return <DreamingView key="dreaming-view" />;
      default:
        return <div key="default-view" className="text-white p-12">Select a module</div>;
    }
  };

  return (
    <div className="flex h-screen bg-black text-white selection:bg-purple-500/30 overflow-hidden">
      <Sidebar activeView={activeView} setActiveView={setActiveView} />
      
      <div className="flex-1 relative overflow-auto p-8 lg:p-12">
        {/* Ambient Background Layer (React Three Fiber) */}
        <AmbientCanvas />

        {/* UI Overlay */}
        <div className="relative z-10 flex flex-col h-full pointer-events-none">
          <Header />

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

          <Footer />
        </div>
      </div>
    </div>
  );
};
