import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Search, Terminal, Cpu, HardDrive, Activity, ArrowDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const LogsView: React.FC = () => {
  const { logs, systemHealth, alerts, healing, betHistory } = useHUD();
  const [filter, setFilter] = useState('');
  const [viewMode, setViewMode] = useState<'timeline' | 'dev'>('timeline');

  // Only show Developer Diagnostics in local dev environment or if manually enabled via localStorage
  const isDevEnvironment = import.meta.env.DEV || (typeof window !== 'undefined' && (
    window.location.hostname === 'localhost' || 
    window.location.hostname === '127.0.0.1' ||
    localStorage.getItem('strike_dev_mode') === 'true'
  ));

  const [activeCategory, setActiveCategory] = useState<'ALL' | 'ALERT' | 'BET' | 'SYSTEM'>('ALL');
  const [wrap, setWrap] = useState(true);
  const [fontSize, setFontSize] = useState<'sm' | 'md' | 'lg'>('sm');
  const logsRef = useRef<HTMLDivElement>(null);
  const [isPinned, setIsPinned] = useState(true);

  const handleScroll = useCallback(() => {
    if (!logsRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = logsRef.current;
    setIsPinned(scrollHeight - scrollTop - clientHeight < 50);
  }, []);

  const scrollToBottom = useCallback(() => {
    if (!logsRef.current) return;
    logsRef.current.scrollTop = logsRef.current.scrollHeight;
    setIsPinned(true);
  }, []);

  useEffect(() => {
    if (logsRef.current && isPinned) {
      logsRef.current.scrollTop = logsRef.current.scrollHeight;
    }
  }, [logs, isPinned]);

  const formatTime = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    } catch {
      return isoString;
    }
  };

  const formatDate = (isoString: string) => {
    try {
      const date = new Date(isoString);
      return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  // Synthesize events for the Operations Timeline
  const timelineEvents = React.useMemo(() => {
    const list: Array<{
      id: string;
      timestamp: string;
      category: 'BET' | 'ALERT' | 'SYSTEM';
      level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS';
      source: string;
      action: string;
      message: string;
    }> = [];

    // 1. Map System Events
    (healing.events || []).forEach(e => {
      list.push({
        id: e.id || `sys-${e.timestamp}-${Math.random()}`,
        timestamp: e.timestamp,
        category: 'SYSTEM',
        level: e.status === 'FAILURE' ? 'ERROR' : e.status === 'SUCCESS' ? 'SUCCESS' : 'INFO',
        source: e.agent || 'System',
        action: e.action || 'EVENT',
        message: e.details || ''
      });
    });

    // 2. Map Alert Events
    (alerts || []).forEach((a: any, idx: number) => {
      const typeLabel = a.type === 'odds_drop' ? 'Odds Drop' : a.type === 'value_bet' ? 'Value Bet' : a.type;
      list.push({
        id: `alert-${a.timestamp}-${idx}`,
        timestamp: a.timestamp,
        category: 'ALERT',
        level: a.type === 'odds_drop' ? 'WARN' : 'INFO',
        source: 'AlertEngine',
        action: (a.type || 'ALERT').toUpperCase(),
        message: `${a.horse} @ ${a.course}: Opportunity detected (${typeLabel} | Odds: ${a.odds})`
      });
    });

    // 3. Map Betting Events
    (betHistory || []).forEach(b => {
      const ts = b.placedAt || new Date().toISOString();
      
      // Placement event
      list.push({
        id: `bet-place-${b.id}`,
        timestamp: ts,
        category: 'BET',
        level: 'INFO',
        source: 'Governor',
        action: 'PLACE_BET',
        message: `Placed R${b.stake.toFixed(2)} on ${b.horse} @ ${b.track} R${b.raceNumber} (Odds: ${b.odds}, Edge: +${b.edgePercent}%)`
      });

      // Settlement event if settled
      if (b.settled) {
        list.push({
          id: `bet-settle-${b.id}`,
          timestamp: ts,
          category: 'BET',
          level: b.won ? 'SUCCESS' : 'WARN',
          source: 'Governor',
          action: b.won ? 'BET_WON' : 'BET_LOST',
          message: `Settled bet on ${b.horse} @ ${b.track} R${b.raceNumber}: ${b.won ? 'WON (+R' + (b.payout || 0).toFixed(2) + ')' : 'LOST'}`
        });
      }
    });

    // Sort descending (newest first)
    return list.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  }, [healing.events, alerts, betHistory]);

  const filteredEvents = timelineEvents.filter(ev => {
    if (activeCategory !== 'ALL' && ev.category !== activeCategory) return false;
    if (!filter) return true;
    const q = filter.toLowerCase();
    return (
      ev.message.toLowerCase().includes(q) ||
      ev.source.toLowerCase().includes(q) ||
      ev.action.toLowerCase().includes(q)
    );
  });

  const filteredLogs = logs.filter(log =>
    filter === '' || log.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-4 md:p-6 space-y-4 md:space-y-6 h-[calc(100vh-160px)] md:h-[calc(100vh-200px)] min-h-[500px] flex flex-col"
    >
      {/* Header and Mode Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 shrink-0">
        <div>
          <h2 className="text-xl md:text-2xl font-bold bg-linear-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
            Telemetry & Logs
          </h2>
          <p className="text-[9px] md:text-xs text-theme-secondary mt-0.5 uppercase tracking-widest font-black">
            {viewMode === 'timeline' ? 'Operations Audit Trail' : 'Raw System Diagnostics'}
          </p>
        </div>
        
        {/* Toggle Button Group */}
        {isDevEnvironment && (
          <div className="flex gap-1.5 bg-black/40 border border-white/10 p-1 rounded-xl w-full sm:w-auto self-start sm:self-auto backdrop-blur-md">
            <button
              onClick={() => setViewMode('timeline')}
              className={`flex-1 sm:flex-none px-3.5 py-1.5 text-[9px] font-black uppercase tracking-wider rounded-lg transition-all ${
                viewMode === 'timeline' 
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/10 border border-purple-500/20' 
                  : 'text-slate-400 hover:text-white border border-transparent'
              }`}
            >
              📋 Operations Feed
            </button>
            <button
              onClick={() => setViewMode('dev')}
              className={`flex-1 sm:flex-none px-3.5 py-1.5 text-[9px] font-black uppercase tracking-wider rounded-lg transition-all ${
                viewMode === 'dev' 
                  ? 'bg-purple-600 text-white shadow-md shadow-purple-600/10 border border-purple-500/20' 
                  : 'text-slate-400 hover:text-white border border-transparent'
              }`}
            >
              🛠️ Dev Diagnostics
            </button>
          </div>
        )}
      </div>

      {/* System Health Cards */}
      <div className="grid grid-cols-3 gap-2 md:gap-4 shrink-0">
        {[
          { label: 'CPU', value: `${systemHealth.cpu.toFixed(1)}%`, icon: Cpu, color: 'text-blue-500' },
          { label: 'MEMORY', value: `${systemHealth.memory.toFixed(1)}%`, icon: HardDrive, color: 'text-indigo-500' },
          { label: 'STATUS', value: systemHealth.status, icon: Activity, color: systemHealth.status === 'ONLINE' ? 'text-emerald-500' : 'text-amber-500' },
        ].map((stat, i) => (
          <div key={i} className="p-3 md:p-4 rounded-xl md:rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl flex flex-col justify-between overflow-hidden">
            <stat.icon className={`w-3.5 h-3.5 md:w-4 md:h-4 ${stat.color} mb-2 md:mb-3`} />
            <div>
              <div className={`text-xs md:text-xl font-black text-theme-primary mb-0.5 tabular truncate ${stat.label === 'STATUS' ? stat.color : ''}`}>
                {stat.value}
              </div>
              <div className="text-[8px] md:text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
            </div>
          </div>
        ))}
      </div>

      {/* Filter and Control Toolbar */}
      <div className="flex flex-col sm:flex-row gap-2.5 shrink-0">
        <div className="relative flex-1">
          <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-secondary" />
          <input
            type="text"
            placeholder={viewMode === 'timeline' ? "SEARCH TIMELINE ACTIONS..." : "FILTER DEV TELEMETRY..."}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full bg-theme-panel border border-theme rounded-2xl py-3 pl-12 pr-4 text-xs font-bold text-theme-primary focus:outline-hidden focus:border-purple-500/50 transition-colors placeholder:text-theme-secondary/30"
          />
        </div>
        
        {/* Console Controls (Dev Mode Only) */}
        {viewMode === 'dev' && (
          <div className="flex gap-2">
            <button
              onClick={() => setWrap(!wrap)}
              className={`flex-1 sm:flex-none px-4 py-2 rounded-2xl border text-[9px] font-black uppercase tracking-wider transition-all flex items-center justify-center gap-1.5 ${
                wrap 
                  ? 'bg-purple-500/10 border-purple-500/30 text-purple-400' 
                  : 'bg-theme-panel border-theme text-theme-secondary hover:text-theme-primary'
              }`}
              title="Toggle Word Wrap"
            >
              Wrap: {wrap ? 'ON' : 'OFF'}
            </button>

            <button
              onClick={() => {
                if (fontSize === 'sm') setFontSize('md');
                else if (fontSize === 'md') setFontSize('lg');
                else setFontSize('sm');
              }}
              className="flex-1 sm:flex-none px-4 py-2 rounded-2xl bg-theme-panel border border-theme text-theme-secondary hover:text-theme-primary text-[9px] font-black uppercase tracking-wider transition-all text-center"
              title="Cycle Font Size"
            >
              Size: {fontSize.toUpperCase()}
            </button>
          </div>
        )}
      </div>

      {/* Timeline Category quick switcher */}
      {viewMode === 'timeline' && (
        <div className="flex gap-1.5 overflow-x-auto pb-1 custom-scrollbar shrink-0">
          {[
            { id: 'ALL', label: 'All Operations', color: 'border-white/10 text-theme-primary' },
            { id: 'BET', label: '💰 Betting Logs', color: 'border-emerald-500/20 text-emerald-400 bg-emerald-500/5' },
            { id: 'ALERT', label: '🚨 Alerts Triggered', color: 'border-red-500/20 text-red-400 bg-red-500/5' },
            { id: 'SYSTEM', label: '⚙️ Sync & Healing', color: 'border-indigo-500/20 text-indigo-400 bg-indigo-500/5' },
          ].map(cat => (
            <button
              key={cat.id}
              onClick={() => setActiveCategory(cat.id as any)}
              className={`px-3 py-1.5 rounded-xl border text-[9px] font-black uppercase tracking-wider whitespace-nowrap transition-all ${
                activeCategory === cat.id
                  ? 'bg-purple-600 border-purple-500 text-white'
                  : `hover:bg-white/5 ${cat.color}`
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      )}

      {/* Main Logs Console Box */}
      <div className="flex-1 min-h-0 relative">
        <div 
          ref={logsRef}
          onScroll={handleScroll}
          className={`absolute inset-0 bg-theme-panel border border-theme rounded-3xl overflow-y-auto p-4 md:p-6 custom-scrollbar`}
        >
          {viewMode === 'timeline' ? (
            /* OPERATIONS TIMELINE FEED */
            <div className="space-y-2.5">
              {filteredEvents.map((ev) => {
                const badgeColor = 
                  ev.category === 'BET' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' :
                  ev.category === 'ALERT' ? 'bg-red-500/10 text-red-400 border-red-500/20' :
                  'bg-indigo-500/10 text-indigo-400 border-indigo-500/20';

                const levelIndicator = 
                  ev.level === 'ERROR' ? 'border-l-2 border-red-500 bg-red-500/5' :
                  ev.level === 'SUCCESS' ? 'border-l-2 border-emerald-500 bg-emerald-500/5' :
                  ev.level === 'WARN' ? 'border-l-2 border-amber-500 bg-amber-500/5' :
                  'border-l-2 border-blue-500 bg-blue-500/5';

                return (
                  <div 
                    key={ev.id} 
                    className={`p-3 md:p-3.5 rounded-2xl border border-white/5 flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 transition-all hover:border-white/10 ${levelIndicator}`}
                  >
                    <div className="flex items-start gap-2.5 min-w-0">
                      <span className={`px-1.5 py-0.5 rounded-md border text-[8px] font-black uppercase tracking-wider shrink-0 mt-0.5 ${badgeColor}`}>
                        {ev.category}
                      </span>
                      <div className="min-w-0">
                        <p className="text-xs font-semibold text-theme-primary tracking-tight leading-snug break-words">
                          {ev.message}
                        </p>
                        <p className="text-[9px] text-slate-500 uppercase font-black tracking-wider mt-1">
                          Source: {ev.source} • Action: {ev.action}
                        </p>
                      </div>
                    </div>
                    
                    <div className="text-right shrink-0 flex items-center sm:flex-col gap-1.5 sm:gap-0.5 self-end sm:self-center">
                      <span className="text-[9px] font-bold text-slate-400 tabular-nums">
                        {formatTime(ev.timestamp)}
                      </span>
                      <span className="text-[8px] font-black text-purple-400 uppercase tracking-widest">
                        {formatDate(ev.timestamp)}
                      </span>
                    </div>
                  </div>
                );
              })}
              
              {filteredEvents.length === 0 && (
                <div className="flex flex-col items-center justify-center h-48 text-theme-secondary space-y-3 opacity-30">
                  <Terminal className="w-10 h-10" />
                  <div className="text-[9px] font-black uppercase tracking-widest">No Events Found</div>
                </div>
              )}
            </div>
          ) : (
            /* RAW DEVELOPER DIAGNOSTICS */
            <div 
              className={`font-mono ${
                wrap ? 'whitespace-pre-wrap break-words' : 'whitespace-pre overflow-x-auto'
              } ${
                fontSize === 'sm' ? 'text-[10px] md:text-[11px]' :
                fontSize === 'md' ? 'text-[12px] md:text-[13px]' :
                'text-[14px] md:text-[15px]'
              } space-y-2`}
            >
              {!isPinned && (
                <button
                  onClick={scrollToBottom}
                  className="sticky bottom-2 z-10 mx-auto flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600/80 text-white text-[10px] font-black uppercase tracking-wider backdrop-blur-md border border-purple-400/30 shadow-lg hover:bg-purple-500 transition-all"
                >
                  <ArrowDown className="w-3 h-3" />
                  Live
                </button>
              )}
              <AnimatePresence initial={false}>
                {filteredLogs.map((log, i) => {
                  const isError = log.includes('ERROR') || log.includes('Exception') || log.includes('failed');
                  const isWarn = log.includes('WARN') || log.includes('warning');
                  const isInfo = log.includes('INFO') || log.includes('SUCCESS');
                  
                  return (
                    <motion.div
                      key={`${i}-${log.substring(0, 20)}`}
                      initial={{ opacity: 0, x: -5 }}
                      animate={{ opacity: 1, x: 0 }}
                      className={`flex gap-3 group items-start py-0.5 px-1.5 rounded transition-colors ${
                        isError ? 'bg-red-500/5 hover:bg-red-500/10' :
                        isWarn ? 'bg-amber-500/5 hover:bg-amber-500/10' :
                        'hover:bg-white/5'
                      }`}
                    >
                      <span className="text-theme-secondary shrink-0 select-none opacity-20 group-hover:opacity-75 transition-opacity text-[9px] w-6 text-right">
                        {(i + 1).toString().padStart(3, '0')}
                      </span>
                      <span className={`leading-relaxed flex-1 ${
                        isError ? 'text-red-400 font-bold' :
                        isWarn ? 'text-amber-400 font-semibold' :
                        isInfo ? 'text-blue-400' :
                        'text-theme-primary opacity-80'
                      }`}>
                        {log}
                      </span>
                    </motion.div>
                  );
                })}
              </AnimatePresence>
              {filteredLogs.length === 0 && (
                <div className="flex flex-col items-center justify-center h-full text-theme-secondary space-y-4 opacity-30 py-12">
                  <Terminal className="w-12 h-12" />
                  <div className="text-[10px] font-black uppercase tracking-[0.3em]">No Telemetry Found</div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.div>
  );
};
