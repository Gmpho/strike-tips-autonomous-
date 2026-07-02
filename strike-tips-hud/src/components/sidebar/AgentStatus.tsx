import React, { useState } from 'react';
import { Power, AlertTriangle, Cpu, Activity, Database } from 'lucide-react';
import { useAgentHealth } from '../../hooks/useAgentHealth';
import { motion } from 'framer-motion';
import { apiFetch } from '../../lib/api-fetch';

export const AgentStatus: React.FC = () => {
  const { health } = useAgentHealth();
  const [isLocked, setIsLocked] = useState(false);

  const toggleLock = async () => {
    const endpoint = isLocked ? '/api/agent/reset' : '/api/agent/kill';
    await apiFetch(endpoint, { method: 'POST' });
    setIsLocked(!isLocked);
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 bg-theme-panel rounded-3xl border border-theme backdrop-blur-2xl mx-2 mb-6 hover:shadow-[0_0_30px_rgba(168,85,247,0.1)] transition-shadow"
    >
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-500" />
          <span className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">Agent Pipeline</span>
        </div>
        <button onClick={toggleLock} aria-label={isLocked ? "Unlock agent pipeline" : "Lock agent pipeline"} className="p-1.5 hover:bg-theme-secondary rounded-lg transition-colors border border-theme">
          {isLocked ? <AlertTriangle className="w-4 h-4 text-red-500" /> : <Power className="w-4 h-4 text-emerald-500" />}
        </button>
      </div>
      
      <div className="space-y-4">
        <div className="flex items-center justify-between p-3 bg-theme-secondary rounded-xl border border-theme">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4 text-theme-secondary" />
            <span className="text-xs font-bold text-theme-primary">Orchestrator</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.orchestrator === 'ready' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
            {health.orchestrator}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-theme-secondary rounded-xl border border-theme">
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 text-theme-secondary" />
            <span className="text-xs font-bold text-theme-primary">Local Model (Ollama)</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.ollama === 'connected' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : health.ollama === 'no_models' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'}`}>
            {health.ollama === 'connected' ? 'CONNECTED' : health.ollama === 'no_models' ? 'NO MODELS' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </motion.div>
  );
};