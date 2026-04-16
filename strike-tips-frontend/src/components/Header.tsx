'use client';

import React from 'react';
import { RefreshCw, Bell, User, History, Wallet } from 'lucide-react';
import { BankrollStatus } from '@/lib/api';

interface HeaderProps {
  status: BankrollStatus | null;
  activeTab: string;
  isRefreshing: boolean;
  onRefresh: () => void;
}

export function Header({ status, activeTab, isRefreshing, onRefresh }: HeaderProps) {
  const getTitle = (tab: string) => {
    const titles: Record<string, string> = {
      dashboard: 'Intelligence Dashboard',
      chat: 'Strike Bot Intelligence',
      races: 'Live Race Tracks',
      search: 'Deep Market Scraper',
      bets: 'Bankroll & Position Manager',
      settings: 'System Configuration',
    };
    return titles[tab] || 'Racing Intelligence';
  };

  return (
    <header className="flex items-center justify-between mb-8">
      <div>
        <h1 className="text-2xl font-bold text-white tracking-tight">{getTitle(activeTab)}</h1>
        <div className="flex items-center gap-2 mt-1">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <p className="text-xs text-slate-400 font-medium tracking-wide first-letter:uppercase">Connected to Live Racing Data</p>
        </div>
      </div>

      <div className="flex items-center gap-6">
        <div className="flex items-center gap-3 glass-effect px-5 py-2.5 rounded-2xl">
          <div className="p-1.5 rounded-lg bg-emerald-500/10 text-emerald-500">
            <Wallet className="w-4 h-4" />
          </div>
          <div className="flex flex-col">
            <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider leading-none mb-1">Available Bankroll</span>
            <span className="text-sm font-bold text-white tabular-numbers leading-none">
              R{status?.current_bankroll?.toLocaleString() || '0.00'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button 
            onClick={onRefresh}
            className={`p-2.5 rounded-xl glass-card text-slate-400 hover:text-white transition-all ${isRefreshing ? 'animate-spin cursor-not-allowed' : ''}`}
            disabled={isRefreshing}
          >
            <RefreshCw className="w-5 h-5" />
          </button>
          
          <button className="p-2.5 rounded-xl glass-card text-slate-400 hover:text-white relative">
            <Bell className="w-5 h-5" />
            <span className="absolute top-2.5 right-2.5 w-1.5 h-1.5 bg-orange-500 border border-[#0f172a] rounded-full" />
          </button>

          <div className="w-px h-6 bg-white/10 mx-1" />

          <button className="flex items-center gap-3 p-1.5 pl-3 rounded-xl glass-card group transition-all">
            <span className="text-sm font-semibold text-slate-200 group-hover:text-white transition-colors">Racing Bot</span>
            <div className="w-8 h-8 rounded-lg bg-slate-800 flex items-center justify-center border border-white/5">
              <User className="w-5 h-5 text-slate-400" />
            </div>
          </button>
        </div>
      </div>
    </header>
  );
}
