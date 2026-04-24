import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Activity } from 'lucide-react';
import { AIChat } from './AIChat';
import { useAgentHealth } from '../hooks/useAgentHealth';
import { motion } from 'framer-motion';

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
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="grid grid-cols-1 xl:grid-cols-3 gap-8 h-full"
    >
      <div className="xl:col-span-1 space-y-6 flex flex-col h-full">
        <div className="flex justify-between items-center mb-2 px-2">
            <h2 className="text-2xl font-black text-white tracking-tight">AI Agent Pipeline</h2>
            <button onClick={() => { void refreshHealth(); void fetchAgents(); }} className="p-2 hover:bg-white/10 rounded-xl transition-colors backdrop-blur-md border border-white/5">
              <RotateCcw className="w-4 h-4 text-purple-400" />
            </button>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-4">
            {agents.map((agent, i) => (
            <motion.div 
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.05 }}
              key={i} 
              className="p-5 bg-white/5 border border-white/10 rounded-3xl flex items-center justify-between backdrop-blur-2xl shadow-[0_0_30px_rgba(0,0,0,0.3)] hover:border-purple-500/30 hover:bg-purple-500/5 transition-all group"
            >
                <div>
                <div className="text-sm font-black text-white mb-1 tracking-tighter uppercase">{agent.name}</div>
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-widest">{agent.model}</div>
                </div>
                <div className="flex items-center gap-4">
                <span className={`flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest ${
                  agent.status === 'online' ? 'text-emerald-500' :
                  agent.status === 'cloud'  ? 'text-blue-400' :
                  'text-red-500'
                }`}>
                    <Activity className={`w-3 h-3 ${agent.status === 'online' ? 'animate-pulse' : ''}`} /> {agent.status}
                </span>
                <button className="p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-xl group-hover:bg-purple-500 group-hover:text-black transition-all">
                    <Play className="w-4 h-4 text-purple-400 group-hover:text-black" />
                </button>
                </div>
            </motion.div>
            ))}
        </div>
      </div>
      
      <div className="xl:col-span-2 h-full">
        <AIChat />
      </div>
    </motion.div>
  );
};
