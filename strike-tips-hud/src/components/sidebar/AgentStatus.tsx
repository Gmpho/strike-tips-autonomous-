import React, { useState } from 'react';
import { Power, AlertTriangle, Cpu, Activity, Database } from 'lucide-react';
import { useAgentHealth } from '../../hooks/useAgentHealth';
import { motion } from 'framer-motion';

export const AgentStatus: React.FC = () => {
  const { health } = useAgentHealth();
  const [isLocked, setIsLocked] = useState(false);

  const toggleLock = async () => {
    const endpoint = isLocked ? '/api/agent/reset' : '/api/agent/kill';
    await fetch(endpoint, { method: 'POST' });
    setIsLocked(!isLocked);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 bg-white/5 rounded-3xl border border-white/10 backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.5)] mx-2 mb-6 hover:shadow-[0_0_30px_rgba(168,85,247,0.1)] transition-shadow"
    >
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-500" />
          <span className="text-[10px] font-black text-slate-300 uppercase tracking-widest">Agent Pipeline</span>
        </div>
        <button onClick={toggleLock} className="p-1.5 hover:bg-white/10 rounded-lg transition-colors border border-transparent hover:border-white/10">
          {isLocked ? <AlertTriangle className="w-4 h-4 text-red-500" /> : <Power className="w-4 h-4 text-emerald-500" />}
        </button>
      </div>
      
      <div className="space-y-4">
        <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-bold text-slate-300">Orchestrator</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.orchestrator === 'ready' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
            {health.orchestrator}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-white/5 rounded-xl border border-white/5">
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 text-slate-400" />
            <span className="text-xs font-bold text-slate-300">Local Model (Ollama)</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.ollama === 'connected' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-red-500/20 text-red-400 border border-red-500/30'}`}>
            {health.ollama}
          </span>
        </div>
      </div>
    </motion.div>
  );
};
