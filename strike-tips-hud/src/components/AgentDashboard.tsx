import React, { useState, useEffect } from 'react';
import { Play, RotateCcw, Activity, MessageSquare, Cpu } from 'lucide-react';
import { AIChat } from './AIChat';
import { useAgentHealth } from '../hooks/useAgentHealth';
import { motion } from 'framer-motion';
import { apiFetch } from '../lib/api-fetch';

interface Agent {
  name: string;
  status: string;
  model: string;
}

export const AgentDashboard: React.FC = () => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [activeTab, setActiveTab] = useState<'chat' | 'swarm'>('chat');
  const { refreshHealth } = useAgentHealth();

  const fetchAgents = async () => {
    try {
      const modelsRes = await apiFetch('/api/agent/models');
      const modelsData = await modelsRes.json();

      if (modelsData.models) {
        setAgents(modelsData.models.map((m: { name?: string; id?: string; type?: string; is_available?: boolean }) => ({
          name: m.name || m.id || 'Unknown',
          status: m.is_available ? 'online' : 'offline',
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
  }, []);

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="flex flex-col space-y-4 h-[calc(100vh-160px)] md:h-[calc(100vh-200px)] min-h-[550px]"
    >
      {/* Premium responsive tab switcher (Visible only below xl) */}
      <div className="flex xl:hidden border border-white/10 bg-black/40 p-1.5 rounded-2xl backdrop-blur-md">
        <button
          onClick={() => setActiveTab('chat')}
          className={`flex-1 py-3 text-[10px] font-black uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 ${
            activeTab === 'chat' 
              ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20 border border-purple-500/30' 
              : 'text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <MessageSquare className="w-3.5 h-3.5" />
          Chat Terminal
        </button>
        <button
          onClick={() => setActiveTab('swarm')}
          className={`flex-1 py-3 text-[10px] font-black uppercase tracking-wider rounded-xl transition-all flex items-center justify-center gap-2 ${
            activeTab === 'swarm' 
              ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20 border border-purple-500/30' 
              : 'text-slate-400 hover:text-white border border-transparent'
          }`}
        >
          <Cpu className="w-3.5 h-3.5" />
          Agent Swarm ({agents.length})
        </button>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6 md:gap-8 flex-1 min-h-0">
        {/* Left Column (Pipeline / Agent List) */}
        <div className={`xl:col-span-1 flex-col space-y-4 h-full min-h-0 ${activeTab === 'swarm' ? 'flex' : 'hidden xl:flex'}`}>
          <div className="flex justify-between items-center px-1">
            <h2 className="text-lg font-black text-white tracking-tight uppercase">AI Agent Pipeline</h2>
            <button 
              onClick={() => { void refreshHealth(); void fetchAgents(); }} 
              className="p-2 hover:bg-white/10 rounded-xl transition-colors backdrop-blur-md border border-white/5"
            >
              <RotateCcw className="w-3.5 h-3.5 text-purple-400" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto custom-scrollbar pr-1 space-y-3">
            {agents.length === 0 && (
              [1, 2, 3].map(i => (
                <div key={i} className="p-4 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-between animate-pulse">
                  <div className="space-y-2">
                    <div className="h-3 w-24 bg-white/10 rounded" />
                    <div className="h-2 w-16 bg-white/5 rounded" />
                  </div>
                  <div className="h-6 w-16 bg-white/10 rounded-xl" />
                </div>
              ))
            )}
            {agents.map((agent, i) => (
              <motion.div 
                initial={{ opacity: 0, x: -10 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: i * 0.03 }}
                key={i} 
                className="p-4 bg-white/5 border border-white/10 rounded-2xl flex items-center justify-between backdrop-blur-2xl shadow-[0_0_20px_rgba(0,0,0,0.2)] hover:border-purple-500/30 hover:bg-purple-500/5 transition-all group"
              >
                <div>
                  <div className="text-xs font-black text-white mb-1 tracking-tighter uppercase">{agent.name}</div>
                  <div className="text-[9px] text-slate-500 font-bold uppercase tracking-widest">{agent.model}</div>
                </div>
                <div className="flex items-center gap-3">
                  <span className={`flex items-center gap-1 text-[9px] font-black uppercase tracking-widest ${
                    agent.status === 'online' ? 'text-emerald-500' :
                    agent.status === 'cloud'  ? 'text-blue-400' :
                    'text-red-500'
                  }`}>
                    <Activity className={`w-2.5 h-2.5 ${agent.status === 'online' ? 'animate-pulse' : ''}`} /> {agent.status}
                  </span>
                  <button className="p-2 bg-purple-500/10 border border-purple-500/20 rounded-xl group-hover:bg-purple-500 group-hover:text-black transition-all">
                    <Play className="w-3.5 h-3.5 text-purple-400 group-hover:text-black" />
                  </button>
                </div>
              </motion.div>
            ))}
          </div>
        </div>
        
        {/* Right Column (AIChat terminal) */}
        <div className={`xl:col-span-2 h-full min-h-0 ${activeTab === 'chat' ? 'block' : 'hidden xl:block'}`}>
          <AIChat />
        </div>
      </div>
    </motion.div>
  );
};

