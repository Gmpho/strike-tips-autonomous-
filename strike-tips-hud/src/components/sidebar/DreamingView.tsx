import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, CloudMoon, Zap, RefreshCcw, Sparkles, Loader2 } from 'lucide-react';
import { Canvas } from '@react-three/fiber';
import { DreamOrb, DreamOrbFallback } from '../visualizer/DreamOrb';
import { apiFetch } from '../../lib/api-fetch';
import { isSoftwareWebGL } from '../../lib/detectSoftwareWebGL';

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

  // Custom dream states
  const [customTrack, setCustomTrack] = useState('Turffontein');
  const [customRaceNum, setCustomRaceNum] = useState(1);
  const [customScenario, setCustomScenario] = useState('heavy rain / wind 25km/h / scratches 3, 5');
  const [simulating, setSimulating] = useState(false);

  const fetchDreams = async () => {
    try {
      const res = await apiFetch(`/api/dreaming/logs`);
      const data = await res.json();
      setDreams(data);
    } catch (e) {
      console.error("Failed to fetch dreams", e);
    }
  };

  const triggerPulse = async () => {
    setIsPulsing(true);
    try {
      await apiFetch(`/api/dreaming/pulse`, { method: 'POST' });
      await fetchDreams();
    } catch (e) {
      console.error(e);
    }
    setTimeout(() => setIsPulsing(false), 2000);
  };

  const triggerCustomDream = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!customTrack || !customScenario) return;
    setSimulating(true);
    try {
      await apiFetch(`/api/dreaming/custom`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          track: customTrack.trim(),
          race_number: Number(customRaceNum),
          scenario: customScenario.trim(),
        }),
      });
      await fetchDreams();
    } catch (err) {
      console.error(err);
    } finally {
      setSimulating(false);
    }
  };

  useEffect(() => {
    fetchDreams();
    const interval = setInterval(fetchDreams, 10000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex flex-col lg:flex-row gap-6 sm:gap-8 w-full p-3.5 sm:p-6 min-h-0">
      {/* Simulation Visualizer & Controls */}
      <div className="flex-1 flex flex-col gap-6 min-w-0">
        <div className="flex-1 min-h-[300px] bg-theme-panel border border-theme rounded-3xl relative overflow-hidden group">
          <div className="absolute inset-0 z-0 flex items-center justify-center">
            {typeof window !== 'undefined' && (window.innerWidth < 1024 || 'ontouchstart' in window || isSoftwareWebGL()) ? (
              <DreamOrbFallback />
            ) : (
              <Canvas
                camera={{ position: [0, 0, 8] }}
                dpr={[1, 1.5]}
                gl={{ 
                  powerPreference: 'low-power', 
                  antialias: false, 
                  stencil: false, 
                  depth: true,
                  alpha: true,
                  preserveDrawingBuffer: false,
                  failIfMajorPerformanceCaveat: true
                }}
                onCreated={(state) => {
                  state.gl.domElement.addEventListener('webglcontextlost', (e) => {
                    e.preventDefault();
                  });
                }}
              >
                <ambientLight intensity={0.5} />
                <pointLight position={[10, 10, 10]} intensity={1.5} color="#a855f7" />
                <DreamOrb />
              </Canvas>
            )}
          </div>

          {/* Overlay Controls */}
          <div className="absolute inset-0 z-10 p-6 flex flex-col justify-between pointer-events-none">
            <div className="flex justify-between items-start pointer-events-auto">
              <div>
                <h2 className="text-2xl font-black text-theme-primary flex items-center gap-3">
                  <CloudMoon className="text-purple-500" /> Neural Dreaming
                </h2>
                <p className="text-theme-secondary text-[10px] font-black uppercase tracking-widest mt-1">
                  Background Simulation Tier 7
                </p>
              </div>
              <button 
                onClick={triggerPulse}
                disabled={isPulsing}
                aria-label={isPulsing ? "Triggering dream pulse" : "Trigger dream pulse"}
                className={`p-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-purple-500 hover:bg-purple-500/20 transition-all cursor-pointer ${isPulsing ? 'animate-pulse' : ''}`}
              >
                <RefreshCcw className={`w-4 h-4 ${isPulsing ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="bg-theme-panel/80 backdrop-blur-xl border border-theme p-4 rounded-xl w-fit shadow-2xl pointer-events-auto">
              <div className="flex items-center gap-4">
                <div className="p-2 rounded-full bg-purple-500/10 flex items-center justify-center">
                  <Brain className="text-purple-500 w-5 h-5" />
                </div>
                <div>
                  <div className="text-[9px] font-black text-theme-secondary uppercase tracking-tighter">Current Simulation</div>
                  <div className="text-xs font-black text-theme-primary">
                    {dreams[0]?.scenario || "Initializing Neural Pathways..."}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Custom Simulation Controls */}
        <form onSubmit={triggerCustomDream} className="bg-theme-panel border border-theme p-6 rounded-3xl space-y-4">
          <div className="flex items-center gap-2 mb-2">
            <Brain className="w-4 h-4 text-purple-500" />
            <h3 className="text-xs font-black text-theme-primary uppercase tracking-widest">Trigger Custom Dream Simulation</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="space-y-1.5">
              <label className="text-[10px] text-theme-secondary font-black uppercase">Track Name</label>
              <input
                type="text"
                value={customTrack}
                onChange={(e) => setCustomTrack(e.target.value)}
                className="w-full bg-theme-secondary border border-theme rounded-xl px-3 py-2 text-xs font-bold text-theme-primary focus:outline-hidden focus:border-purple-500"
                placeholder="e.g. Greyville"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] text-theme-secondary font-black uppercase">Race Number</label>
              <input
                type="number"
                value={customRaceNum}
                onChange={(e) => setCustomRaceNum(Number(e.target.value))}
                min="1"
                max="12"
                className="w-full bg-theme-secondary border border-theme rounded-xl px-3 py-2 text-xs font-bold text-theme-primary focus:outline-hidden focus:border-purple-500"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-[10px] text-theme-secondary font-black uppercase">Scenario Conditions</label>
              <input
                type="text"
                value={customScenario}
                onChange={(e) => setCustomScenario(e.target.value)}
                className="w-full bg-theme-secondary border border-theme rounded-xl px-3 py-2 text-xs font-bold text-theme-primary focus:outline-hidden focus:border-purple-500"
                placeholder="e.g. heavy rain / wind 25km/h"
              />
            </div>
          </div>
          <div className="flex justify-end pt-2">
            <button
              type="submit"
              disabled={simulating}
              className="flex items-center gap-2 bg-purple-500/20 text-purple-300 border border-purple-500/30 hover:bg-purple-500/30 font-black px-6 py-2.5 rounded-xl text-xs uppercase tracking-wider cursor-pointer transition-all disabled:opacity-50"
            >
              {simulating ? (
                <><Loader2 className="w-3.5 h-3.5 animate-spin" /> Running Dream Simulation...</>
              ) : (
                <><Sparkles className="w-3.5 h-3.5" /> Launch Custom Dream</>
              )}
            </button>
          </div>
        </form>
      </div>

      {/* Dream Logs */}
      <div className="w-full lg:w-96 flex flex-col gap-4">
        <div className="px-2 flex items-center justify-between">
          <h3 className="text-xs font-black text-theme-secondary uppercase tracking-widest">Neural Logs</h3>
          <div className="flex items-center gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-500 animate-pulse" />
            <span className="text-[10px] font-black text-purple-500 uppercase tracking-tighter">Synced</span>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto space-y-3 custom-scrollbar">
          <AnimatePresence mode="popLayout">
            {dreams.map((dream, idx) => (
              <motion.div
                key={dream.id}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: idx * 0.05 }}
                className="bg-theme-panel border border-theme p-5 rounded-2xl hover:bg-theme-secondary transition-all group"
              >
                <div className="flex justify-between items-start mb-3">
                  <span className="text-[10px] font-black text-theme-secondary tabular">
                    {new Date(dream.timestamp).toLocaleTimeString([], { hour12: false })}
                  </span>
                  <div className={`px-2 py-0.5 rounded text-[9px] font-black flex items-center gap-1 ${
                    dream.probability_shift > 0 ? 'bg-emerald-500/10 text-emerald-500 border border-emerald-500/20' : 'bg-rose-500/10 text-rose-500 border border-rose-500/20'
                  }`}>
                    {dream.probability_shift > 0 ? '+' : ''}{(dream.probability_shift * 100).toFixed(1)}% EDGE
                  </div>
                </div>
                <p className="text-sm font-black text-theme-primary mb-3 leading-tight group-hover:text-purple-500 transition-colors">
                  {dream.scenario}
                </p>
                <div className="flex items-center gap-3 text-[10px] text-theme-secondary bg-theme-secondary/30 p-3 rounded-xl border border-theme">
                  <Zap className="w-3 h-3 text-amber-500 shrink-0" />
                  <span className="italic font-bold">{dream.insight}</span>
                </div>
                
                {/* Vividness Bar */}
                <div className="mt-4 h-1.5 w-full bg-theme-secondary rounded-full overflow-hidden border border-theme/50">
                  <motion.div 
                    initial={{ width: 0 }}
                    animate={{ width: `${dream.vividness * 100}%` }}
                    className="h-full bg-linear-to-r from-purple-500 to-indigo-500 shadow-[0_0_8px_rgba(168,85,247,0.4)]"
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
