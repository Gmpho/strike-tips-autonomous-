'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { 
  TrendingUp, Activity, DollarSign, ShieldCheck, Zap, 
  MapPin, Clock, ChevronDown, Sparkles, Loader2 
} from 'lucide-react';
import { Virtuoso } from 'react-virtuoso';
import { RaceCard } from '@/components/RaceCard';
import { 
  getStatus, getTracks, getMonitoringSnapshot, analyzeRace, getSystemHealth,
  BankrollStatus, L7Health
} from '@/lib/api';
import { Sidebar } from '@/components/Sidebar';
import { Header } from '@/components/Header';
import { L7Diagnostics } from '@/components/L7Diagnostics';
import { ViewTransition } from 'react';

type Tab = 'dashboard' | 'chat' | 'races' | 'search' | 'bets' | 'settings';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [status, setStatus] = useState<BankrollStatus | null>(null);
  const [tracks, setTracks] = useState<{tracks: string[], today_tracks: string[]} | null>(null);
  const [monitoringData, setMonitoringData] = useState<any>(null);
  const [health, setHealth] = useState<L7Health | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setIsRefreshing(true);
    try {
      const [s, t, m, h] = await Promise.all([
        getStatus(), 
        getTracks(), 
        getMonitoringSnapshot(),
        getSystemHealth()
      ]);
      setStatus(s);
      setTracks(t);
      setMonitoringData(m);
      setHealth(h);
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
         setActiveTab(tab as Tab);
      }} />

      <main className="flex-1 flex flex-col overflow-hidden">
        <div className="flex-1 overflow-y-auto p-4 lg:p-10 custom-scrollbar">
          <div className="flex flex-col lg:flex-row lg:items-center justify-between mb-8">
            <div className="flex-1">
              <Header 
                status={status} 
                activeTab={activeTab} 
                isRefreshing={isRefreshing} 
                onRefresh={loadData} 
              />
            </div>
            <L7Diagnostics health={health} />
          </div>

          <ViewTransition>
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

  const events = monitoringData?.events ? Object.values(monitoringData.events) : [];

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

          <div className="grid grid-cols-1 gap-4" style={{ height: '700px' }}>
            {events.length > 0 ? (
              <Virtuoso
                style={{ height: '100%' }}
                data={events}
                itemContent={(index, race: any) => (
                  <div className="pr-4 pb-4">
                    <RaceCard 
                      race={race}
                      isExpanded={expandedRaceId === race.id}
                      isAnalyzing={analyzingRaceId === race.id}
                      analysis={analysisResults[race.id]}
                      onToggle={() => setExpandedRaceId(expandedRaceId === race.id ? null : race.id)}
                      onAnalyze={handleAnalyze}
                    />
                  </div>
                )}
              />
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
                {monitoringData?.alerts && monitoringData.alerts.length > 0 ? (
                  monitoringData.alerts.map((alert: any, i: number) => (
                    <div key={`alert-${i}`} className="flex gap-4 group">
                       <div className="flex flex-col items-center">
                          <div className={`w-2 h-2 rounded-full ${alert.condition_type === 'value_bet' ? 'bg-emerald-500 animate-pulse' : 'bg-rose-500'}`} />
                          <div className="flex-1 w-px bg-slate-800" />
                       </div>
                       <div className="pb-4">
                          <p className="text-[10px] font-bold text-slate-500 mb-0.5 uppercase tracking-widest tabular-numbers">{alert.triggered_at ? new Date(alert.triggered_at).toLocaleTimeString() : 'LIVE'}</p>
                          <p className="text-sm font-bold text-white mb-1">{alert.race_course} • {alert.horse_name || 'Market Shift'}</p>
                          <p className={`text-xs font-semibold px-2 py-1 rounded-md inline-block bg-white/5 border border-white/10 ${alert.condition_type === 'value_bet' ? 'text-emerald-400' : 'text-rose-400'}`}>
                            {alert.condition_type === 'value_bet' ? 'Value Bet Detected' : 'Threshold Breached'}
                          </p>
                       </div>
                    </div>
                  ))
                ) : (
                  [1, 2, 3].map((i) => (
                    <div key={i} className="flex gap-4 group">
                       <div className="flex flex-col items-center">
                          <div className="w-1.5 h-1.5 rounded-full bg-slate-700 group-first:bg-amber-500" />
                          <div className="flex-1 w-px bg-slate-800" />
                       </div>
                       <div className="pb-4">
                          <p className="text-[10px] font-bold text-slate-500 mb-0.5 uppercase tracking-widest tabular-numbers">Awaiting Data</p>
                          <p className="text-xs text-slate-400 leading-relaxed font-medium">Scanning passive intelligence streams...</p>
                       </div>
                    </div>
                  ))
                )}
             </div>
          </div>
        </section>
      </div>
    </div>
  );
}
