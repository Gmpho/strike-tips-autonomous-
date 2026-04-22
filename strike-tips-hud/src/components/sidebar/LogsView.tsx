import React, { useEffect, useState, useRef } from 'react';
import { Terminal, Cpu, HardDrive, Activity, RefreshCw, Search } from 'lucide-react';

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
    <div className="p-8 animate-in fade-in duration-500 h-full flex flex-col">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-2xl font-black text-white tracking-tight flex items-center gap-3">
          <Terminal className="w-6 h-6 text-purple-500" />
          System Logs
        </h2>
        <button 
          onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 rounded-lg bg-white/5 text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          <span className="text-sm">Refresh</span>
        </button>
      </div>

      {/* System Health Cards */}
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <Cpu className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">CPU</span>
          </div>
          <div className="text-2xl font-black text-white">{health?.cpu_usage_percent?.toFixed(1) || '0.0'}%</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <HardDrive className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Memory</span>
          </div>
          <div className="text-2xl font-black text-white">{health?.memory_usage_percent?.toFixed(1) || '0.0'}%</div>
        </div>

        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
          <div className="flex items-center gap-2 text-slate-500 mb-2">
            <Activity className="w-4 h-4" />
            <span className="text-xs font-black uppercase tracking-wider">Status</span>
          </div>
          <div className={`text-2xl font-black ${health?.status === 'HEALTHY' ? 'text-emerald-400' : 'text-amber-400'}`}>
            {health?.status || 'UNKNOWN'}
          </div>
        </div>
      </div>

      {/* Filter Input */}
      <div className="relative mb-4">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Filter logs..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full bg-white/5 border border-white/10 rounded-xl pl-10 pr-4 py-3 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-purple-500/50"
        />
      </div>

      {/* Log Output */}
      <div className="flex-1 bg-black/60 border border-white/10 rounded-xl overflow-hidden">
        <div className="px-4 py-2 border-b border-white/10 bg-white/5 flex items-center justify-between">
          <span className="text-xs font-black text-slate-500 uppercase tracking-wider">
            {filteredLogs.length} entries
          </span>
        </div>
        <div 
          ref={logsRef}
          className="p-4 font-mono text-xs text-slate-400 overflow-y-auto max-h-[400px]"
        >
          {filteredLogs.length === 0 ? (
            <div className="text-slate-600">No logs available</div>
          ) : (
            filteredLogs.map((log, i) => (
              <div key={i} className="py-0.5 hover:bg-white/5 px-2 -mx-2 rounded">
                <span className="text-slate-600 mr-2">[{new Date().toLocaleTimeString()}]</span>
                <span className="text-slate-300">{log}</span>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};