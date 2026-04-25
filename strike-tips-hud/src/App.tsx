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
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
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
        <div key="loading-state" className="flex-1 flex flex-col items-center justify-center p-12">
          <div className="w-16 h-16 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin mb-4" />
          <p className="text-slate-500 font-black uppercase tracking-widest animate-pulse">Initializing Neural Link...</p>
        </div>
      );
    }

    switch (activeView) {
      case 'dashboard':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
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
    <div className="min-h-screen bg-theme-primary text-theme-primary selection:bg-purple-500/30">
      {/* Ambient Background Layer (Fixed) */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <AmbientCanvas />
      </div>

      <div className="flex">
        {/* Sidebar - Sticky to allow independent scroll if needed but usually fits */}
        <aside className={`${isSidebarCollapsed ? 'w-20' : 'w-64'} h-screen sticky top-0 shrink-0 border-r border-theme bg-theme-panel backdrop-blur-2xl transition-all duration-300 ease-in-out z-30`}>
          <Sidebar 
            activeView={activeView} 
            setActiveView={setActiveView} 
            isCollapsed={isSidebarCollapsed}
            onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
          />
        </aside>

        <main className="flex-1 min-w-0 relative z-10 flex flex-col">
          {/* Header - Sticky Top */}
          <div className="sticky top-0 z-20 px-8 lg:px-12 pt-6 lg:pt-8 pb-4 backdrop-blur-md bg-theme-panel border-b border-theme">
            <Header />
          </div>

          {/* Main Content Area - Natural Scroll */}
          <div className="px-8 lg:px-12 py-8 flex-1">
            <div className="w-full">
              <AnimatePresence mode="wait">
                <motion.div 
                  key={activeView}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  {renderView()}
                </motion.div>
              </AnimatePresence>
            </div>

            {/* Footer follows content naturally */}
            <Footer />
          </div>
        </main>
      </div>
    </div>
  );
};
