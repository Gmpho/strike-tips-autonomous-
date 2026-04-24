import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Activity } from 'lucide-react';
import { AIChat } from './AIChat';
import { useAgentHealth } from '../hooks/useAgentHealth';

interface Agent {
  name: string;
  status: string;
  model: string;
}

export const AgentDashboard: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const { health, refreshHealth } = useAgentHealth();

  const fetchAgents = async () => {
    try {
      const modelsRes = await fetch('/api/agent/models');
      const modelsData = await modelsRes.json();
      const ollamaOnline = health.ollama === 'connected';

      if (modelsData.models) {
        setAgents(modelsData.models.map((m: { name?: string; id?: string; type?: string }) => ({
          name: m.name || m.id || 'Unknown',
          status: m.type === 'local' ? (ollamaOnline ? 'online' : 'offline') : 'cloud',
          model: m.id || 'N/A',
        })));
      }
    } catch (e) {
      console.error("Failed to fetch agents", e);
    }
  };

  useEffect(() => {
    void fetchAgents();
    const interval = setInterval(fetchAgents, 25000);
    return () => clearInterval(interval);
  }, [health.ollama]);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-8 animate-in fade-in duration-500 h-full">
      <div className="xl:col-span-1 space-y-6">
        <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-black text-white uppercase tracking-tighter">AI Agent Pipeline</h2>
            <button onClick={() => { void refreshHealth(); void fetchAgents(); }} className="p-2 hover:bg-white/10 rounded-full transition-colors">
            <RotateCcw className="w-4 h-4 text-purple-400" />
            </button>
        </div>

        <div className="grid grid-cols-1 gap-4">
            {agents.map((agent, i) => (
            <div key={i} className="p-5 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-between">
                <div>
                <div className="text-xs font-black text-white">{agent.name}</div>
                <div className="text-[10px] text-slate-500 font-bold uppercase">{agent.model}</div>
                </div>
                <div className="flex items-center gap-3">
                <span className={`flex items-center gap-1.5 text-[10px] font-black uppercase ${
                  agent.status === 'online' ? 'text-emerald-500' :
                  agent.status === 'cloud'  ? 'text-blue-400' :
                  'text-red-500'
                }`}>
                    <Activity className="w-3 h-3" /> {agent.status}
                </span>
                <button className="p-2 bg-purple-500/20 rounded-lg hover:bg-purple-500/40">
                    <Play className="w-3 h-3 text-purple-400" />
                </button>
                </div>
            </div>
            ))}
        </div>
      </div>
      
      <div className="xl:col-span-2">
        <AIChat />
      </div>
    </div>
  );
};
