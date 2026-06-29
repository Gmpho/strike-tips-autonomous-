import * as React from 'react';
import { useEffect, useState } from 'react';
import { useHUD } from './hooks/useHUD';
import { useTelegram } from './hooks/useTelegram';
import { apiFetch } from './lib/api-fetch';
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
import { MarketMoversView } from './components/sidebar/MarketMoversView';
import { PredictorView } from './components/sidebar/PredictorView';
import { ResultsView } from './components/sidebar/ResultsView';
import { AmbientCanvas } from './components/visualizer/AmbientCanvas';
import { WebGLErrorBoundary } from './components/visualizer/WebGLErrorBoundary';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { LegalPage } from './components/LegalPage';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

const LEGAL_VIEWS = ['privacy', 'terms', 'disclaimer', 'how-to-bet', 'faq', 'betting-rules', 'responsible'];
const VALID_VIEWS = [
  'dashboard', 'agents', 'bankroll', 'analytics', 'logs', 'settings',
  'healing', 'vitals', 'dreaming', 'market-movers', 'predictor', 'results',
  ...LEGAL_VIEWS
];

function getViewFromPath(): string {
  const path = window.location.pathname.slice(1); // remove leading /
  return VALID_VIEWS.includes(path) ? path : 'dashboard';
}

export const App: React.FC = () => {
  const [activeView, setActiveView] = useState(() => getViewFromPath());

  // Sync URL with activeView
  useEffect(() => {
    const handlePopState = () => setActiveView(getViewFromPath());
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const navigate = (view: string) => {
    setActiveView(view);
    window.history.pushState(null, '', `/${view}`);
    localStorage.setItem('strike_active_view', view);
  };
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const state = useHUD();
  useTelegram();

  // Load backend configuration at startup to sync sound prompts state to localStorage
  useEffect(() => {
    apiFetch('/api/config')
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (data && data.soundEnabled !== undefined) {
          localStorage.setItem('strike_sound_enabled', String(data.soundEnabled));
        }
        if (data && data.valueBetAlerts !== undefined) {
          localStorage.setItem('strike_value_bet_alerts', String(data.valueBetAlerts));
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    localStorage.setItem('strike_active_view', activeView);
  }, [activeView]);

  useEffect(() => {
    if (state.systemHealth.cpu > 60) {
      document.body.classList.add('low-power');
    } else {
      document.body.classList.remove('low-power');
    }
  }, [state.systemHealth.cpu]);

  const handleMobileNav = (view: string) => {
    navigate(view);
    setIsMobileMenuOpen(false);
  };

  const renderView = () => {
    const hasCachedData = Object.keys(state.events).length > 0 || (state.bankroll && state.bankroll.balance > 0);

    if (!hasCachedData && activeView === 'dashboard') {
      return (
        <div key="loading-state" className="flex-1 flex flex-col items-center justify-center p-6 md:p-12">
          <div className="w-12 h-12 md:w-16 md:h-16 border-4 border-purple-500/20 border-t-purple-500 rounded-full animate-spin mb-4" />
          <p className="text-slate-500 font-black uppercase tracking-widest animate-pulse text-xs md:text-sm">Initializing Neural Link...</p>
        </div>
      );
    }

    switch (activeView) {
      case 'dashboard':
        return (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
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
      case 'market-movers':
        return <MarketMoversView key="market-movers-view" />;
      case 'predictor':
        return <PredictorView key="predictor-view" />;
      case 'results':
        return <ResultsView key="results-view" />;
      case 'privacy':
        return <LegalPage key="privacy-view" docId="privacy" title="Privacy Policy" />;
      case 'terms':
        return <LegalPage key="terms-view" docId="terms" title="Terms of Service" />;
      case 'disclaimer':
        return <LegalPage key="disclaimer-view" docId="disclaimer" title="Disclaimer" />;
      case 'how-to-bet':
        return <LegalPage key="how-to-bet-view" docId="how-to-bet" title="How to Bet" />;
      case 'faq':
        return <LegalPage key="faq-view" docId="faq" title="FAQ" />;
      case 'betting-rules':
        return <LegalPage key="betting-rules-view" docId="betting-rules" title="Betting Rules" />;
      case 'responsible':
        return <LegalPage key="responsible-view" docId="responsible" title="Responsible Gambling" />;
      default:
        return <div key="default-view" className="text-white p-12">Select a module</div>;
    }
  };

  return (
    <div className="min-h-screen bg-theme-primary text-theme-primary selection:bg-purple-500/30">
      {/* Ambient Background Layer (Fixed) */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <WebGLErrorBoundary>
          <AmbientCanvas />
        </WebGLErrorBoundary>
      </div>

      {/* Mobile menu overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="fixed inset-0 z-50 bg-black/60 backdrop-blur-sm md:hidden"
            onClick={() => setIsMobileMenuOpen(false)}
          >
            <motion.aside
              initial={{ x: -320 }}
              animate={{ x: 0 }}
              exit={{ x: -320 }}
              transition={{ type: "spring", damping: 25, stiffness: 300 }}
              className="w-72 h-full bg-theme-panel border-r border-theme overflow-y-auto"
              onClick={e => e.stopPropagation()}
            >
              <div className="flex justify-end p-4">
                <button
                  onClick={() => setIsMobileMenuOpen(false)}
                  className="p-2 rounded-lg bg-theme-secondary hover:bg-purple-500/10 text-theme-secondary hover:text-purple-500 transition-all border border-theme"
                >
                  <X size={18} />
                </button>
              </div>
              <Sidebar
                activeView={activeView}
                setActiveView={handleMobileNav}
                isCollapsed={false}
                onToggle={() => setIsMobileMenuOpen(false)}
              />
            </motion.aside>
          </motion.div>
        )}
      </AnimatePresence>

      <div className="flex flex-col md:flex-row">
        {/* Desktop sidebar */}
        <aside className="hidden md:block">
          <div className={`${isSidebarCollapsed ? 'w-0 overflow-hidden opacity-0 px-0' : 'w-64'} h-screen sticky top-0 shrink-0 border-r border-theme bg-theme-panel backdrop-blur-2xl transition-all duration-300 ease-in-out z-30`}>
            <Sidebar
              activeView={activeView}
              setActiveView={setActiveView}
              isCollapsed={isSidebarCollapsed}
              onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            />
          </div>
        </aside>

        <main className="flex-1 min-w-0 relative z-10 flex flex-col">
          {/* Header */}
          <div className="sticky top-0 z-20 px-4 md:px-8 lg:px-12 pt-4 md:pt-6 lg:pt-8 pb-3 md:pb-4 backdrop-blur-md bg-theme-panel border-b border-theme">
            <Header
              onToggleSidebar={() => setIsMobileMenuOpen(true)}
              isSidebarCollapsed={isSidebarCollapsed}
            />
          </div>

          {/* Main Content */}
          <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8 flex-1 flex flex-col min-h-0">
            <div className="w-full flex-1 flex flex-col min-h-0">
              <AnimatePresence mode="wait">
                <motion.div
                  key={activeView}
                  className="flex-1 flex flex-col min-h-0"
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  transition={{ duration: 0.2 }}
                >
                  {renderView()}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>

          {/* Footer */}
          <Footer />
        </main>
      </div>
    </div>
  );
};
