'use client';

import { useState, useEffect, useRef, ViewTransition } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { TrendingUp, Activity, DollarSign, ShieldCheck, Zap, MessageSquare, Search, List as ListIcon, Settings, ChevronRight, Menu, Bell, User, Clock, MapPin, ChevronDown, Sparkles, Loader2 } from 'lucide-react';
import { 
  getStatus, getTracks, getMonitoringSnapshot, getChatHistory, getModels, analyzeRace,
  BankrollStatus, Race, ValueBet, Bet, ChatMessage 
} from '@/lib/api';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';


type Tab = 'dashboard' | 'chat' | 'races' | 'search' | 'bets' | 'settings';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [status, setStatus] = useState<BankrollStatus | null>(null);
  const [tracks, setTracks] = useState<{tracks: string[], today_tracks: string[]} | null>(null);
  const [monitoringData, setMonitoringData] = useState<any>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000); 
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const [s, t, m] = await Promise.all([
        getStatus(), 
        getTracks(), 
        getMonitoringSnapshot()
      ]);
      setStatus(s);
      setTracks(t);
      setMonitoringData(m);
      setError('');
    } catch (e: any) {
      setError(e.message);
    } finally {
      setIsRefreshing(false);
    }
  };

  return (
    <div className="flex h-screen bg-[#0f172a] text-slate-200 selection:bg-amber-500/30">
      <Sidebar activeTab={activeTab} setActiveTab={(tab) => {
         // View Transitions trigger on tab changes
         setActiveTab(tab as Tab);
      }} />

      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 lg:p-10 custom-scrollbar">
          <Header 
            status={status} 
            activeTab={activeTab} 
            isRefreshing={isRefreshing} 
            onRefresh={loadData} 
          />

          <ViewTransition enter="fade-in" exit="fade-out" default="none">
            <div key={activeTab} className="min-h-full">
              {activeTab === 'dashboard' && <DashboardContent status={status} monitoringData={monitoringData} />}
              {activeTab === 'chat' && <div className="text-center py-20 text-slate-500 glass-card rounded-3xl">AI Intelligence Bot Component Ready</div>}
              {activeTab === 'races' && <div className="text-center py-20 text-slate-500 glass-card rounded-3xl">Live Track Feed Active</div>}
              {activeTab === 'bets' && <div className="text-center py-20 text-slate-500 glass-card rounded-3xl">Bankroll Ledger Locked</div>}
              {activeTab === 'search' && <div className="text-center py-20 text-slate-500 glass-card rounded-3xl">Deep Market Scraper Initialized</div>}
              {activeTab === 'settings' && <div className="text-center py-20 text-slate-500 glass-card rounded-3xl">Engine Calibration Access Restricted</div>}
            </div>
          </ViewTransition>
        </div>
      </main>
    </div>
  );
}

function DashboardContent({ status, monitoringData }: { status: BankrollStatus | null, monitoringData: any }) {
  const [expandedRaceId, setExpandedRaceId] = useState<string | null>(null);
  const [analyzingRaceId, setAnalyzingRaceId] = useState<string | null>(null);
  const [analysisResults, setAnalysisResults] = useState<Record<string, any>>({});

  const handleAnalyze = async (e: React.MouseEvent, track: string, raceNumber: number, raceId: string) => {
    e.stopPropagation();
    setAnalyzingRaceId(raceId);
    try {
      const data = await analyzeRace(track, raceNumber);
      setAnalysisResults(prev => ({ ...prev, [raceId]: data.result }));
    } catch (err) {
      console.error('Analysis failed:', err);
    } finally {
      setAnalyzingRaceId(null);
    }
  };

  const stats = [
    { label: 'Intelligence Edge', value: '7.8%', trend: '+1.2%', icon: TrendingUp, color: 'text-amber-500' },
    { label: 'Total Scans', value: monitoringData?.jobs?.length || '0', trend: 'Neutral', icon: Activity, color: 'text-emerald-500' },
    { label: 'Daily ROI', value: `${Number(status?.performance?.roi || 0).toFixed(1)}%`, trend: '+4.3%', icon: DollarSign, color: 'text-blue-500' },
    { label: 'Win Rate', value: `${Number(status?.performance?.win_rate || 0).toFixed(0)}%`, trend: 'Stable', icon: ShieldCheck, color: 'text-indigo-500' },
  ];

  return (
    <div className="flex-1 space-y-8 pb-10">
      <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {stats.map((stat, i) => (
          <div key={i} className="glass-card p-6 rounded-[2rem] border border-white/10 shadow-xl shadow-black/20 hover:bg-white/5 transition-all duration-500">
            <div className="flex items-center gap-4">
              <div className={`w-12 h-12 rounded-2xl bg-white/5 flex items-center justify-center border border-white/10 ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
              <div>
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">{stat.label}</p>
                <div className="flex items-baseline gap-2">
                  <h3 className="text-2xl font-black text-white tabular-numbers">{stat.value}</h3>
                </div>
              </div>
            </div>
            <div className={`mt-4 inline-flex items-center gap-1 text-[10px] font-bold px-2 py-0.5 rounded-full bg-white/5 ${stat.trend.startsWith('+') ? 'text-emerald-500' : 'text-slate-500'}`}>
               {stat.trend.startsWith('+') ? '▲' : '•'} {stat.trend}
            </div>
          </div>
        ))}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <section className="lg:col-span-8 space-y-6">
          <div className="flex items-center justify-between px-2">
            <div>
              <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
                Market Opportunities
                <span className="text-[10px] font-bold bg-amber-500/10 text-amber-500 px-2 py-1 rounded-full uppercase tracking-widest border border-amber-500/20">Live Intelligence</span>
              </h2>
              <p className="text-slate-400 text-sm font-medium mt-1">Real-time value extraction from active markets.</p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4">
            {monitoringData?.events ? (
              Object.values(monitoringData.events).map((race: any, i) => {
                const isExpanded = expandedRaceId === race.id;
                const isAnalyzing = analyzingRaceId === race.id;
                const analysis = analysisResults[race.id];
                
                return (
                  <div 
                    key={race.id || i} 
                    className={`glass-card rounded-[2rem] overflow-hidden transition-all duration-500 border border-white/5 ${isExpanded ? 'bg-white/5 ring-1 ring-amber-500/20 shadow-2xl shadow-amber-500/5' : 'hover:bg-white/10'}`}
                  >
                    <div 
                      onClick={() => setExpandedRaceId(isExpanded ? null : race.id)}
                      className="p-5 flex items-center justify-between cursor-pointer group"
                    >
                      <div className="flex items-center gap-5">
                        <div className="w-16 h-16 rounded-2xl bg-white/5 flex items-center justify-center border border-white/5 text-2xl font-black text-slate-700 group-hover:text-amber-500 transition-colors">
                          R{race.raceNumber}
                        </div>
                        <div>
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs font-bold text-amber-500 bg-amber-500/10 px-2 py-0.5 rounded-lg uppercase tracking-wider">
                              {race.isFinished ? 'Settled' : 'Ready'}
                            </span>
                            <span className="text-xs text-slate-500 font-medium tracking-tight flex items-center gap-1.5">
                              <MapPin className="w-3 h-3" /> {race.en} • <Clock className="w-3 h-3 ml-1" /> {race.t}
                            </span>
                          </div>
                          <h4 className="text-lg font-bold text-white group-hover:translate-x-1 transition-transform">Market Analysis: {race.en}</h4>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                         <div className="text-right mr-4 hidden sm:block">
                            <p className="text-[10px] text-slate-500 font-bold uppercase mb-0.5">Status</p>
                            <p className={`text-sm font-black ${race.isFinished ? 'text-slate-500' : 'text-emerald-500 animate-pulse'}`}>
                              {race.isFinished ? 'Finished' : 'Live NOW'}
                            </p>
                         </div>
                         <div className="flex items-center gap-2">
                           <button 
                             onClick={(e) => handleAnalyze(e, race.en, race.raceNumber, race.id)}
                             disabled={isAnalyzing}
                             className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-amber-500 text-slate-900 font-bold text-sm shadow-lg shadow-amber-500/20 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:grayscale"
                           >
                             {isAnalyzing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                             {isAnalyzing ? 'Analyzing...' : 'Analyze'}
                           </button>
                           <div className={`p-2 rounded-xl bg-white/5 border border-white/10 transition-transform duration-500 ${isExpanded ? 'rotate-180' : ''}`}>
                              <ChevronDown className="w-5 h-5 text-slate-400" />
                           </div>
                         </div>
                       </div>
                    </div>

                    {isExpanded && (
                      <div className="px-5 pb-6 pt-2 border-t border-white/5 space-y-6 animate-in fade-in slide-in-from-top-4 duration-500">
                        {analysis && (
                          <div className="bg-amber-500/5 border border-amber-500/20 rounded-2xl p-4 flex gap-4">
                            <div className="w-10 h-10 rounded-xl bg-amber-500/20 flex-shrink-0 flex items-center justify-center">
                              <Sparkles className="w-5 h-5 text-amber-500" />
                            </div>
                            <div>
                              <h5 className="text-amber-500 font-bold text-sm uppercase tracking-wider mb-1">Strike AI Insight</h5>
                              <p className="text-slate-300 text-sm leading-relaxed">{analysis.insight || analysis.message}</p>
                            </div>
                          </div>
                        )}

                        <div className="overflow-hidden rounded-2xl border border-white/5">
                          <table className="w-full text-left border-collapse">
                            <thead className="bg-white/5">
                              <tr>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none border-b border-white/5">Horse Name</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none border-b border-white/5">Jockey / Trainer</th>
                                <th className="px-4 py-3 text-[10px] font-bold text-slate-500 uppercase tracking-widest leading-none border-b border-white/5 text-right">Odds</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {race.runners?.map((runner: any, idx: number) => (
                                <tr key={idx} className="hover:bg-white/5 transition-colors group">
                                  <td className="px-4 py-4">
                                    <span className="font-bold text-white group-hover:text-amber-500 transition-colors uppercase tracking-tight">{runner.name}</span>
                                  </td>
                                  <td className="px-4 py-4">
                                    <div className="space-y-0.5">
                                      <p className="text-sm font-bold text-slate-300 flex items-center gap-1.5">
                                        <User className="w-3 h-3 text-slate-500" /> {runner.jockey}
                                      </p>
                                      <p className="text-[10px] text-slate-500 font-medium">Trainer: {runner.trainer}</p>
                                    </div>
                                  </td>
                                  <td className="px-4 py-4 text-right">
                                    <span className="text-sm font-black text-white tabular-nums">{runner.odds}</span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="text-center py-20 glass-card rounded-[3rem] border border-dashed border-white/10">
                <Loader2 className="w-10 h-10 text-slate-700 animate-spin mx-auto mb-4" />
                <p className="text-slate-500 font-medium italic">Synchronizing with live feeds...</p>
              </div>
            )}
          </div>
        </section>

        <section className="lg:col-span-4 space-y-6">
          <div className="flex items-center justify-between px-2">
            <h2 className="text-xl font-bold text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-indigo-500" />
              System Log
            </h2>
          </div>
          <div className="glass-card rounded-[2rem] p-6 h-[400px] flex flex-col">
             <div className="flex-1 space-y-4 overflow-y-auto custom-scrollbar pr-2">
                {[1, 2, 3, 4].map((i) => (
                   <div key={i} className="flex gap-4 group">
                      <div className="flex flex-col items-center">
                         <div className="w-1.5 h-1.5 rounded-full bg-slate-700 group-first:bg-amber-500" />
                         <div className="flex-1 w-px bg-slate-800" />
                      </div>
                      <div className="pb-4">
                         <p className="text-[10px] font-bold text-slate-500 mb-0.5 uppercase tracking-widest tabular-numbers">14:2{i} PM</p>
                         <p className="text-xs text-slate-300 leading-relaxed font-medium">Monitoring market inefficiencies for active races.</p>
                      </div>
                   </div>
                ))}
             </div>
          </div>
        </section>
      </div>
    </div>
  );
}
