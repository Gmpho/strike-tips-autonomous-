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
        <div className="animate-pulse text-purple-500">Loading system logs...</div>
      </div>
    );
  }

  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="p-8 h-full flex flex-col"
    >
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
          <Terminal className="w-6 h-6 text-purple-500" />
          System Logs
        </h2>
        <button 
          onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition-colors backdrop-blur-md border border-white/10"
        >
          <RefreshCw className="w-4 h-4" />
          <span className="text-sm">Refresh</span>
        </button>
      </div>

      {/* System Health Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <motion.div 
          whileHover={{ y: -5, scale: 1.02 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <Cpu className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">CPU</span>
          </div>
          <div className="text-4xl font-black text-white">{health?.cpu_usage_percent?.toFixed(1) || '0.0'}%</div>
        </motion.div>

        <motion.div 
          whileHover={{ y: -5, scale: 1.02 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <HardDrive className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Memory</span>
          </div>
          <div className="text-4xl font-black text-white">{health?.memory_usage_percent?.toFixed(1) || '0.0'}%</div>
        </motion.div>

        <motion.div 
          whileHover={{ y: -5, scale: 1.02 }}
          className="bg-white/5 border border-white/10 rounded-3xl p-6 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)]"
        >
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <Activity className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Status</span>
          </div>
          <div className={`text-4xl font-black ${health?.status === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`}>
            {health?.status || 'UNKNOWN'}
          </div>
        </motion.div>
      </div>

      {/* Filter Input */}
      <div className="relative mb-6">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-500" />
        <input
          type="text"
          placeholder="Filter logs..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full bg-white/5 border border-white/10 rounded-2xl pl-12 pr-4 py-4 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.3)] transition-all"
        />
      </div>

      {/* Log Output */}
      <div className="flex-1 bg-black/40 border border-white/10 rounded-3xl overflow-hidden backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] flex flex-col">
        <div className="px-6 py-4 border-b border-white/10 bg-white/5 flex items-center justify-between">
          <span className="text-xs font-black text-slate-500 uppercase tracking-widest">
            {filteredLogs.length} entries
          </span>
        </div>
        <div 
          ref={logsRef}
          className="flex-1 p-6 font-mono text-xs text-slate-400 overflow-y-auto custom-scrollbar"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-slate-600">No logs available</div>
          ) : (
            filteredLogs.map((log, i) => (
              <motion.div 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.2 }}
                key={i} 
                className="py-1 hover:bg-white/5 px-2 -mx-2 rounded transition-colors"
              >
                <span className="text-slate-600 mr-2">[{new Date().toLocaleTimeString()}]</span>
                <span className="text-slate-300">{log}</span>
              </motion.div>
            ))
          )}
        </div>
      </div>
    </motion.div>
  );
};