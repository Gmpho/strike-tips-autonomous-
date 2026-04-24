import React, { useState } from 'react';
import { Power, AlertTriangle } from 'lucide-react';
import { useAgentHealth } from '../../hooks/useAgentHealth';

export const AgentStatus: React.FC = () => {
  const { health } = useAgentHealth();
  const [isLocked, setIsLocked] = useState(false);

  const toggleLock = async () => {
    const endpoint = isLocked ? '/api/agent/reset' : '/api/agent/kill';
    await fetch(endpoint, { method: 'POST' });
    setIsLocked(!isLocked);
  };

  return (
    <div className="p-4 bg-white/5 rounded-xl border border-white/10 mt-6 mx-2">
      <div className="flex items-center justify-between mb-3">
        <span className="text-[9px] font-black text-slate-500 uppercase">Agent Pipeline</span>
        <button onClick={toggleLock} className="p-1 hover:bg-white/10 rounded">
          {isLocked ? <AlertTriangle className="w-3 h-3 text-red-500" /> : <Power className="w-3 h-3 text-emerald-500" />}
        </button>
      </div>
      
      <div className="space-y-2">
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-400">Orchestrator</span>
          <span className={health.orchestrator === 'ready' ? 'text-emerald-500' : 'text-amber-500'}>
            {health.orchestrator}
          </span>
        </div>
        <div className="flex items-center justify-between text-[10px]">
          <span className="text-slate-400">Local Model (Ollama)</span>
          <span className={health.ollama === 'connected' ? 'text-emerald-500' : 'text-red-500'}>
            {health.ollama}
          </span>
        </div>
      </div>
    </div>
  );
};
