import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CloudMoon, Zap, RefreshCcw } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { DreamOrb } from '../visualizer/DreamOrb';

interface Dream {
  id: string;
  timestamp: string;
  scenario: string;
  probability_shift: number;
  insight: string;
  vividness: number;
}

export const DreamingView: React.FC = () => {
  const [dreams, setDreams] = useState<Dream[]>([]);
  const [isPulsing, setIsPulsing] = useState(false);

  const fetchDreams = async () => {
    try {
      const res = await fetch(`/api/dreaming/logs`);
      const data = await res.json();
      setDreams(data);
    } catch (e) {
      console.error("Failed to fetch dreams", e);
    }
  };

  const triggerPulse = async () => {
    setIsPulsing(true);
    try {
      await fetch(`/api/dreaming/pulse`, { method: 'POST' });
      await fetchDreams();
    } catch (e) {
      console.error(e);
    }
    setTimeout(() => setIsPulsing(false), 2000);
  };

  useEffect(() => {
    fetchDreams();
    const interval = setInterval(fetchDreams, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-8 h-full">
      {/* Simulation Visualizer */}
      <div className="flex-1 min-h-[400px] bg-linear-to-br from-purple-900/20 to-black border border-purple-500/10 rounded-3xl relative overflow-hidden group">
        <div className="absolute inset-0 z-0">
          <Canvas camera={{ position: [0, 0, 8] }}>
            <ambientLight intensity={0.5} />
            <pointLight position={[10, 10, 10]} intensity={1.5} color="#a855f7" />
            <DreamOrb />
          </Canvas>
        </div>

        {/* Overlay Controls */}
        <div className="absolute inset-0 z-10 p-8 flex flex-col justify-between pointer-events-none">
          <div className="flex justify-between items-start pointer-events-auto">
            <div>
              <h2 className="text-2xl font-black text-white flex items-center gap-3">
                <CloudMoon className="text-purple-400" /> Neural Dreaming
              </h2>
              <p className="text-slate-400 text-sm font-bold uppercase tracking-widest mt-1">
                Background Simulation Tier 7
              </p>
            </div>
            <button 
              onClick={triggerPulse}
              disabled={isPulsing}
              className={`p-4 rounded-2xl bg-purple-500/20 border border-purple-500/30 text-purple-400 hover:bg-purple-500/30 transition-all ${isPulsing ? 'animate-pulse' : ''}`}
            >
              <RefreshCcw className={`w-5 h-5 ${isPulsing ? 'animate-spin' : ''}`} />
            </button>
          </div>

          <div className="bg-black/60 backdrop-blur-xl border border-white/5 p-6 rounded-2xl w-fit">
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 rounded-full bg-purple-500/20 flex items-center justify-center">
                <Brain className="text-purple-400" />
              </div>
              <div>
                <div className="text-[10px] font-black text-slate-500 uppercase tracking-tighter">Current Simulation</div>
                <div className="text-sm font-bold text-white">
                  {dreams[0]?.scenario || "Initializing Neural Pathways..."}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Dream Logs */}
      <div className="w-full lg:w-96 flex flex-col gap-4">
        <div className="px-2 flex items-center justify-between">
          <h3 className="text-xs font-black text-slate-500 uppercase tracking-[0.2em]">Neural Logs</h3>
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
            <span className="text-[10px] font-bold text-purple-400">SYNCED</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto pr-2 space-y-3 custom-scrollbar">
          <AnimatePresence mode="popLayout">
            {dreams.map((dream, idx) => (
              <motion.div
                key={dream.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: idx * 0.05 }}
                className="bg-white/5 border border-white/10 p-5 rounded-2xl hover:bg-white/10 transition-all group"
              >
                <div className="flex justify-between items-start mb-2">
                  <span className="text-[10px] font-mono font-bold text-slate-500">{dream.timestamp}</span>
                  <div className={`px-2 py-0.5 rounded-full text-[9px] font-black flex items-center gap-1 ${
                    dream.probability_shift > 0 ? 'bg-emerald-500/20 text-emerald-400' : 'bg-rose-500/20 text-rose-400'
                  }`}>
                    {dream.probability_shift > 0 ? '+' : ''}{(dream.probability_shift * 100).toFixed(1)}% EDGE
                  </div>
                </div>
                <p className="text-sm font-bold text-white mb-2 leading-tight">
                  {dream.scenario}
                </p>
                <div className="flex items-center gap-2 text-[11px] text-slate-400 bg-black/40 p-2 rounded-lg border border-white/5">
                  <Zap className="w-3 h-3 text-amber-400 shrink-0" />
                  <span className="italic">{dream.insight}</span>
                </div>
                
                {/* Vividness Bar */}
                <div className="mt-3 h-1 w-full bg-white/5 rounded-full overflow-hidden">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${dream.vividness * 100}%` }}
                    className="h-full bg-linear-to-r from-purple-500 to-indigo-500"
                  />
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>
    </div>
  );
};
