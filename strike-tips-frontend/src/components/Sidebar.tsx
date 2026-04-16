'use client';

import React, { ViewTransition } from 'react';
import { 
  LayoutDashboard, Search, Wallet, History, MessageSquare, Settings, 
  Bot, Menu, ChevronRight, Power, ShieldCheck
} from 'lucide-react';
import { motion } from 'framer-motion';

type Tab = 'dashboard' | 'chat' | 'races' | 'search' | 'bets' | 'settings';

interface SidebarProps {
  activeTab: Tab;
  setActiveTab: (tab: Tab) => void;
  isLocked?: boolean;
}

export function Sidebar({ activeTab, setActiveTab, isLocked }: SidebarProps) {
  const menuItems = [
    { id: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { id: 'chat', icon: MessageSquare, label: 'Strike Bot', badge: 'AI' },
    { id: 'races', icon: ShieldCheck, label: 'Live Tracks' },
    { id: 'search', icon: Search, label: 'Deep Scraper' },
    { id: 'bets', icon: Wallet, label: 'Bankroll' },
    { id: 'settings', icon: Settings, label: 'Intelligence' },
  ];

  return (
    <ViewTransition name="persistent-nav">
      <aside className="w-64 h-screen border-r border-white/5 bg-slate-900/50 backdrop-blur-xl flex flex-col p-4">
        <div className="flex items-center gap-3 px-2 mb-10">
          <div className="w-10 h-10 rounded-xl overflow-hidden shadow-lg shadow-orange-600/20">
            <img src="/logo.png" alt="Strike Tips Logo" className="w-full h-full object-cover" />
          </div>
          <div>
            <h2 className="text-lg font-bold tracking-tight text-white leading-tight uppercase">Strike Tips</h2>
            <p className="text-[10px] text-amber-500/80 font-bold uppercase tracking-widest">Racing Engine</p>
          </div>
        </div>

        <nav className="flex-1 space-y-1">
          {menuItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id as Tab)}
              className={`w-full flex items-center justify-between px-4 py-3 rounded-xl transition-all duration-200 group ${
                activeTab === item.id 
                ? 'bg-amber-500/10 text-amber-500 shadow-sm' 
                : 'text-slate-400 hover:text-slate-100 hover:bg-white/5'
              }`}
            >
              <div className="flex items-center gap-3">
                <item.icon className={`w-5 h-5 ${activeTab === item.id ? 'text-amber-500' : 'group-hover:text-slate-100'}`} />
                <span className="text-sm font-medium">{item.label}</span>
              </div>
              {item.badge && (
                <span className="px-1.5 py-0.5 rounded-md bg-amber-500/20 text-amber-500 text-[10px] font-bold">
                  {item.badge}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="mt-auto pt-6 border-t border-white/5 space-y-4">
          <div className="glass-card p-4 rounded-2xl relative overflow-hidden group cursor-pointer">
            <div className="relative z-10">
              <div className="flex items-center justify-between mb-2">
                <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">System Status</span>
                <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              </div>
              <p className="text-xs font-medium text-slate-200">Engine Fully Optimized</p>
            </div>
            <div className="absolute inset-0 bg-gradient-to-br from-amber-500/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
          </div>

          <button className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-500/5 transition-all group">
            <Power className="w-5 h-5 group-hover:rotate-90 transition-transform duration-500" />
            <span className="text-sm font-medium">Terminate Session</span>
          </button>
        </div>
      </aside>
    </ViewTransition>
  );
}
