import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Cpu, HardDrive, Activity, RefreshCw, Search } from 'lucide-react';
import { motion } from 'framer-motion';

interface LogEntry {
  logs: string[];
  count: number;
  source: string;
  error?: string;
}

interface SystemHealth {
  cpu_usage_percent: number;
  memory_usage_percent: number;
  available_memory_mb: number;
  status: string;
  timestamp: string;
}

export const LogsView: React.FC = () => {
  const [logs, setLogs] = useState<string[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const logsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [logsRes, healthRes] = await Promise.all([
          fetch('/api/logs?tail=100'),
          fetch('/api/system/health')
        ]);
        
        if (logsRes.ok) {
          const logsData: LogEntry = await logsRes.json();
          setLogs(logsData.logs || []);
        }
        
        if (healthRes.ok) {
          const healthData: SystemHealth = await healthRes.json();
          setHealth(healthData);
        }
      } catch (err) {
        console.error('Failed to fetch logs:', err);
      } finally {
        setLoading(false);
      }
    };
    
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  const filteredLogs = logs.filter(log => 
    filter === '' || log.toLowerCase().includes(filter.toLowerCase())
  );

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-pulse text-purple-500 font-black uppercase tracking-widest text-xs">
          Loading Logs...
        </div>
      </div>
    );
  }

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
          { label: 'CPU', value: `${health?.cpu_usage_percent?.toFixed(1) || '0.0'}%`, icon: Cpu, color: 'text-blue-500' },
          { label: 'MEMORY', value: `${health?.memory_usage_percent?.toFixed(1) || '0.0'}%`, icon: HardDrive, color: 'text-indigo-500' },
          { label: 'STATUS', value: health?.status || 'UNKNOWN', icon: Activity, color: health?.status === 'HEALTHY' ? 'text-emerald-500' : 'text-amber-500' },
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
          placeholder="Filter logs..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full bg-theme-panel border border-theme rounded-xl pl-12 pr-4 py-3 text-sm text-theme-primary placeholder-theme-secondary focus:outline-none focus:border-purple-500/50 backdrop-blur-xl transition-all"
        />
      </div>

      {/* Log Output */}
      <div className="flex-1 bg-theme-panel border border-theme rounded-2xl overflow-hidden backdrop-blur-2xl flex flex-col min-h-0">
        <div className="px-4 py-2 border-b border-theme bg-theme-secondary/30 flex items-center justify-between">
          <span className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
            {filteredLogs.length} entries detected
          </span>
          <Terminal className="w-3 h-3 text-theme-secondary" />
        </div>
        <div 
          ref={logsRef}
          className="flex-1 p-4 font-mono text-[10px] overflow-y-auto custom-scrollbar"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-theme-secondary font-bold text-center py-8">NO LOG ENTRIES MATCH FILTER</div>
          ) : (
            filteredLogs.map((log, i) => (
              <motion.div 
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                key={i} 
                className="py-1 border-b border-theme/30 last:border-0 hover:bg-theme-secondary/20 px-2 -mx-2 rounded transition-colors flex gap-3"
              >
                <span className="text-theme-secondary font-black whitespace-nowrap">
                  [{new Date().toLocaleTimeString([], { hour12: false })}]
                </span>
                <span className="text-theme-primary font-medium break-all">{log}</span>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </motion.div>
  );
};