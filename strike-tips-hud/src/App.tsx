import * as React from 'react';
import { useEffect, useState, Suspense } from 'react';
import { useHUD } from './hooks/useHUD';
import { useTelegram } from './hooks/useTelegram';
import { usePWA } from './hooks/usePWA';
import { UpdateToast } from './components/UpdateToast';
import { apiFetch } from './lib/api-fetch';
import type { RaceEvent } from './types';
import { Sidebar } from './components/sidebar/Sidebar.tsx';
import { WebGLErrorBoundary } from './components/visualizer/WebGLErrorBoundary';
import { Header } from './components/layout/Header';
import { Footer } from './components/layout/Footer';
import { RaceCard } from './components/RaceCard.tsx';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

// Lazy-loaded view components — split into separate chunks
const AmbientCanvas = React.lazy(() => import('./components/visualizer/AmbientCanvas').then(m => ({ default: m.AmbientCanvas })));
const AgentDashboard = React.lazy(() => import('./components/AgentDashboard').then(m => ({ default: m.AgentDashboard })));
const BankrollView = React.lazy(() => import('./components/sidebar/BankrollView').then(m => ({ default: m.BankrollView })));
const LogsView = React.lazy(() => import('./components/sidebar/LogsView').then(m => ({ default: m.LogsView })));
const SettingsView = React.lazy(() => import('./components/sidebar/SettingsView').then(m => ({ default: m.SettingsView })));
const AnalyticsView = React.lazy(() => import('./components/sidebar/AnalyticsView').then(m => ({ default: m.AnalyticsView })));
const HealingView = React.lazy(() => import('./components/sidebar/HealingView').then(m => ({ default: m.HealingView })));
const SystemVitalsView = React.lazy(() => import('./components/sidebar/SystemVitalsView').then(m => ({ default: m.SystemVitalsView })));
const DreamingView = React.lazy(() => import('./components/sidebar/DreamingView').then(m => ({ default: m.DreamingView })));
const MarketMoversView = React.lazy(() => import('./components/sidebar/MarketMoversView').then(m => ({ default: m.MarketMoversView })));
const PredictorView = React.lazy(() => import('./components/sidebar/PredictorView').then(m => ({ default: m.PredictorView })));
const ResultsView = React.lazy(() => import('./components/sidebar/ResultsView').then(m => ({ default: m.ResultsView })));
const LegalPage = React.lazy(() => import('./components/LegalPage').then(m => ({ default: m.LegalPage })));
const AIChat = React.lazy(() => import('./components/AIChat').then(m => ({ default: m.AIChat })));
const ExoticsView = React.lazy(() => import('./components/ExoticsView').then(m => ({ default: m.ExoticsView })));

const ViewFallback = () => (
  <div className="flex-1 flex items-center justify-center min-h-[300px]">
    <div className="w-8 h-8 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
  </div>
);

const LEGAL_VIEWS = ['privacy', 'terms', 'disclaimer', 'how-to-bet', 'faq', 'betting-rules', 'responsible'];
const VALID_VIEWS = [
  'dashboard', 'agents', 'chat', 'exotics', 'bankroll', 'analytics', 'logs', 'settings',
  'healing', 'vitals', 'dreaming', 'market-movers', 'predictor', 'results',
  ...LEGAL_VIEWS
];

function getViewFromPath(): string {
  const path = window.location.pathname.slice(1); // remove leading /
  if (VALID_VIEWS.includes(path)) {
    return path;
  }
  const saved = typeof localStorage !== 'undefined' ? localStorage.getItem('strike_active_view') : null;
  return saved && VALID_VIEWS.includes(saved) ? saved : 'dashboard';
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
  const [showAllRaces, setShowAllRaces] = useState(false);
  const [pendingRaceEvent, setPendingRaceEvent] = useState<RaceEvent | null>(null);
  const state = useHUD();
  useTelegram();
  const { hasUpdate, updateSW } = usePWA();

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

    const events = Object.values(state.events);
    const MAX_VISIBLE_CARDS = 18;
    const visibleEvents = showAllRaces ? events : events.slice(0, MAX_VISIBLE_CARDS);

    switch (activeView) {
      case 'dashboard':
        return (
          <div className="flex flex-col gap-4">
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4 md:gap-6">
              {visibleEvents.map((event, idx) => (
                <RaceCard
                  key={event.id}
                  event={event as RaceEvent}
                  idx={idx}
                  onExecutePosition={(ev) => {
                    setPendingRaceEvent(ev);
                    navigate('chat');
                  }}
                />
              ))}
            </div>
            {events.length > MAX_VISIBLE_CARDS && !showAllRaces && (
              <button
                onClick={() => setShowAllRaces(true)}
                className="mx-auto py-3 px-8 bg-purple-500/10 border border-purple-500/30 hover:bg-purple-500/20 rounded-2xl text-purple-300 hover:text-white transition-all text-xs font-black uppercase tracking-wider"
              >
                Show All {events.length} Races
              </button>
            )}
          </div>
        );
      case 'agents':
        return <Suspense key="agents-view" fallback={<ViewFallback />}><AgentDashboard /></Suspense>;
      case 'chat':
        return <Suspense key="chat-view" fallback={<ViewFallback />}><AIChat initialRaceEvent={pendingRaceEvent ?? undefined} /></Suspense>;
      case 'exotics':
        return <Suspense key="exotics-view" fallback={<ViewFallback />}><ExoticsView /></Suspense>;
      case 'bankroll':
        return <Suspense key="bankroll-view" fallback={<ViewFallback />}><BankrollView /></Suspense>;
      case 'analytics':
        return <Suspense key="analytics-view" fallback={<ViewFallback />}><AnalyticsView /></Suspense>;
      case 'logs':
        return <Suspense key="logs-view" fallback={<ViewFallback />}><LogsView /></Suspense>;
      case 'settings':
        return <Suspense key="settings-view" fallback={<ViewFallback />}><SettingsView /></Suspense>;
      case 'healing':
        return <Suspense key="healing-view" fallback={<ViewFallback />}><HealingView /></Suspense>;
      case 'vitals':
        return <Suspense key="vitals-view" fallback={<ViewFallback />}><SystemVitalsView /></Suspense>;
      case 'dreaming':
        return <Suspense key="dreaming-view" fallback={<ViewFallback />}><DreamingView /></Suspense>;
      case 'market-movers':
        return <Suspense key="market-movers-view" fallback={<ViewFallback />}><MarketMoversView /></Suspense>;
      case 'predictor':
        return <Suspense key="predictor-view" fallback={<ViewFallback />}><PredictorView /></Suspense>;
      case 'results':
        return <Suspense key="results-view" fallback={<ViewFallback />}><ResultsView /></Suspense>;
      case 'privacy':
        return <Suspense key="privacy-view" fallback={<ViewFallback />}><LegalPage docId="privacy" title="Privacy Policy" /></Suspense>;
      case 'terms':
        return <Suspense key="terms-view" fallback={<ViewFallback />}><LegalPage docId="terms" title="Terms of Service" /></Suspense>;
      case 'disclaimer':
        return <Suspense key="disclaimer-view" fallback={<ViewFallback />}><LegalPage docId="disclaimer" title="Disclaimer" /></Suspense>;
      case 'how-to-bet':
        return <Suspense key="how-to-bet-view" fallback={<ViewFallback />}><LegalPage docId="how-to-bet" title="How to Bet" /></Suspense>;
      case 'faq':
        return <Suspense key="faq-view" fallback={<ViewFallback />}><LegalPage docId="faq" title="FAQ" /></Suspense>;
      case 'betting-rules':
        return <Suspense key="betting-rules-view" fallback={<ViewFallback />}><LegalPage docId="betting-rules" title="Betting Rules" /></Suspense>;
      case 'responsible':
        return <Suspense key="responsible-view" fallback={<ViewFallback />}><LegalPage docId="responsible" title="Responsible Gambling" /></Suspense>;
      default:
        return <div key="default-view" className="text-white p-12">Select a module</div>;
    }
  };

  return (
    <div className="min-h-screen bg-theme-primary text-theme-primary selection:bg-purple-500/30">
      {/* Ambient Background Layer (Fixed) */}
      <div className="fixed inset-0 z-0 pointer-events-none">
        <WebGLErrorBoundary>
          <Suspense fallback={<div className="absolute inset-0 z-0 pointer-events-none"
            style={{background: 'radial-gradient(ellipse at center, rgba(168,85,247,0.08) 0%, transparent 70%)'}} />}>
            <AmbientCanvas />
          </Suspense>
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
          <div className={`${isSidebarCollapsed ? 'w-0 overflow-hidden opacity-0 px-0' : 'w-64'} h-screen sticky top-0 shrink-0 border-r border-theme bg-theme-panel transition-all duration-300 ease-in-out z-30`}>
            <Sidebar
              activeView={activeView}
              setActiveView={navigate}
              isCollapsed={isSidebarCollapsed}
              onToggle={() => setIsSidebarCollapsed(!isSidebarCollapsed)}
            />
          </div>
        </aside>

        <main className="flex-1 min-w-0 relative z-10 flex flex-col">
          {/* Header */}
          <div className="sticky top-0 z-20 px-4 md:px-8 lg:px-12 pt-4 md:pt-6 lg:pt-8 pb-3 md:pb-4 bg-theme-panel border-b border-theme">
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

      <UpdateToast visible={hasUpdate} onUpdate={updateSW} />
    </div>
  );
};
