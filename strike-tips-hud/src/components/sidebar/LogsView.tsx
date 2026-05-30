import React, { useState, useRef, useEffect, useCallback } from 'react';
import { Search, Terminal, RefreshCw, Cpu, HardDrive, Activity, ArrowDown } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';

export const LogsView: React.FC = () => {
  const { logs, systemHealth } = useHUD();
  const [filter, setFilter] = useState('');
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

  if (systemHealth.status === 'OFFLINE' && logs.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-purple-500 font-black uppercase tracking-widest text-xs">
          Loading Logs...
        </div>
      </div>
    );
  }

  const filteredLogs = logs.filter(log =>
    filter === '' || log.toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-6 space-y-8 h-full flex flex-col"
    >
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-purple-400 to-indigo-400 bg-clip-text text-transparent">
            System Logs
          </h2>
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
            Real-time Agent Telemetry
          </p>
        </div>
        <button
          onClick={() => window.location.reload()}
          className="p-3 rounded-xl bg-theme-panel border border-theme text-theme-secondary hover:text-theme-primary hover:bg-theme-secondary transition-all"
        >
          <RefreshCw className="w-5 h-5" />
        </button>
      </div>

      {/* System Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {[
          { label: 'CPU', value: `${systemHealth.cpu.toFixed(1)}%`, icon: Cpu, color: 'text-blue-500' },
          { label: 'MEMORY', value: `${systemHealth.memory.toFixed(1)}%`, icon: HardDrive, color: 'text-indigo-500' },
          { label: 'STATUS', value: systemHealth.status, icon: Activity, color: systemHealth.status === 'ONLINE' ? 'text-emerald-500' : 'text-amber-500' },
        ].map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className={`text-xl font-black text-theme-primary mb-0.5 tabular ${stat.label === 'STATUS' ? stat.color : ''}`}>
              {stat.value}
            </div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Filter Input */}
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-theme-secondary" />
        <input
          type="text"
          placeholder="FILTER TELEMETRY..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full bg-theme-panel border border-theme rounded-2xl py-4 pl-12 pr-4 text-xs font-black text-theme-primary focus:outline-hidden focus:border-purple-500/50 transition-colors placeholder:text-theme-secondary/30"
        />
      </div>

      {/* Logs Console */}
      <div className="flex-1 min-h-0 relative">
        <div 
          ref={logsRef}
          onScroll={handleScroll}
          className="absolute inset-0 bg-theme-panel border border-theme rounded-3xl overflow-y-auto p-6 font-mono text-[11px] selection:bg-purple-500/30 custom-scrollbar"
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
          <div className="space-y-2">
            <AnimatePresence initial={false}>
              {filteredLogs.map((log, i) => (
                <motion.div
                  key={`${i}-${log.substring(0, 20)}`}
                  initial={{ opacity: 0, x: -5 }}
                  animate={{ opacity: 1, x: 0 }}
                  className="flex gap-4 group"
                >
                  <span className="text-theme-secondary shrink-0 select-none opacity-30 group-hover:opacity-100 transition-opacity">
                    {(i + 1).toString().padStart(3, '0')}
                  </span>
                  <span className={`break-all leading-relaxed ${
                    log.includes('ERROR') ? 'text-red-400 font-bold' :
                    log.includes('WARN') ? 'text-amber-400' :
                    log.includes('INFO') ? 'text-blue-400' :
                    'text-theme-primary opacity-80'
                  }`}>
                    {log}
                  </span>
                </motion.div>
              ))}
            </AnimatePresence>
            {filteredLogs.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-theme-secondary space-y-4 opacity-30 py-12">
                <Terminal className="w-12 h-12" />
                <div className="text-[10px] font-black uppercase tracking-[0.3em]">No Telemetry Found</div>
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
};
