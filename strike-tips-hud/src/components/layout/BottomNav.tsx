import React from 'react';
import { LayoutDashboard, Bot, Ticket, Wallet, Menu } from 'lucide-react';
import { motion } from 'framer-motion';

interface BottomNavProps {
  activeView: string;
  setActiveView: (view: string) => void;
  onOpenMenu: () => void;
  liveRacesCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeView,
  setActiveView,
  onOpenMenu,
  liveRacesCount = 0,
}) => {
  const tabs = [
    { id: 'dashboard', label: 'Races', icon: LayoutDashboard, badge: liveRacesCount > 0 ? liveRacesCount : undefined },
    { id: 'chat', label: 'AI Chat', icon: Bot },
    { id: 'exotics', label: 'Exotics', icon: Ticket },
    { id: 'bankroll', label: 'Bankroll', icon: Wallet },
  ];

  return (
    <nav 
      aria-label="Mobile Navigation"
      className="md:hidden fixed bottom-0 left-0 right-0 z-40 bg-theme-panel/95 backdrop-blur-xl border-t border-theme/80 pb-[max(env(safe-area-inset-bottom),0.5rem)] pt-1.5 px-3 shadow-[0_-10px_25px_rgba(0,0,0,0.5)]"
    >
      <div className="flex items-center justify-around max-w-lg mx-auto">
        {tabs.map((tab) => {
          const isActive = activeView === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              onClick={() => setActiveView(tab.id)}
              className={`relative flex flex-col items-center justify-center py-1.5 px-3 rounded-2xl transition-all select-none min-w-[58px] ${
                isActive ? 'text-purple-400' : 'text-theme-secondary hover:text-theme-primary opacity-80 hover:opacity-100'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
              {isActive && (
                <motion.div
                  layoutId="activeTabIndicator"
                  className="absolute inset-0 bg-purple-500/15 border border-purple-500/30 rounded-2xl -z-10 shadow-[0_0_15px_rgba(168,85,247,0.25)]"
                  transition={{ type: 'spring', stiffness: 380, damping: 30 }}
                />
              )}

              <div className="relative">
                <Icon className={`w-5 h-5 transition-transform ${isActive ? 'scale-110 text-purple-400' : ''}`} />
                {tab.badge !== undefined && (
                  <span className="absolute -top-1.5 -right-2 px-1 py-0.2 bg-emerald-500 text-black text-[8px] font-black rounded-full min-w-[14px] text-center shadow-xs">
                    {tab.badge}
                  </span>
                )}
              </div>

              <span className="text-[10px] font-black tracking-tight uppercase mt-1">
                {tab.label}
              </span>
            </button>
          );
        })}

        {/* Menu Button */}
        <button
          onClick={onOpenMenu}
          className="flex flex-col items-center justify-center py-1.5 px-3 rounded-2xl transition-all select-none min-w-[58px] text-theme-secondary hover:text-theme-primary opacity-80 hover:opacity-100"
          aria-label="Open full menu"
        >
          <Menu className="w-5 h-5" />
          <span className="text-[10px] font-black tracking-tight uppercase mt-1">
            More
          </span>
        </button>
      </div>
    </nav>
  );
};
