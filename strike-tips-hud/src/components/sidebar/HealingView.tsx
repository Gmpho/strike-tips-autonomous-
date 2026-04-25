import React from 'react';
import { motion } from 'framer-motion';
import { Activity, ShieldCheck, Zap, GitBranch, Terminal } from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';

export const HealingView: React.FC = () => {
  const { healing } = useHUD();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-6 space-y-8"
    >
      {/* Header Section */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold bg-linear-to-r from-emerald-400 to-cyan-400 bg-clip-text text-transparent">
            Healing Swarm
          </h2>
          <p className="text-xs text-slate-400 mt-1 uppercase tracking-widest font-medium">
            Autonomous Agent Pipeline Monitoring
          </p>
        </div>
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={() => fetch('/api/healing/pulse', { method: 'POST' })}
          className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 hover:bg-emerald-500/20 transition-colors shadow-[0_0_15px_rgba(16,185,129,0.1)]"
        >
          <Zap className="w-5 h-5 fill-current" />
        </motion.button>
      </div>

      {/* Grid: Agent Stats & Selector Health */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Selector Health Card */}
        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800/50 backdrop-blur-xl group hover:border-emerald-500/30 transition-all duration-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-200">Adaptive Selectors</h3>
          </div>
          
          <div className="space-y-4">
            {Object.entries(healing.selectors).slice(0, 3).map(([field, selectors]) => {
              const bestSelector = Object.entries(selectors)[0];
              const successRate = parseFloat(bestSelector[1].success_rate);
              return (
                <div key={field} className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-slate-400 capitalize">{field.replace('_', ' ')}</span>
                    <span className={successRate > 90 ? 'text-emerald-400' : 'text-amber-400'}>
                      {bestSelector[1].success_rate}
                    </span>
                  </div>
                  <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${successRate}%` }}
                      transition={{ duration: 1, ease: "easeOut" }}
                      className={`h-full rounded-full ${
                        successRate > 90 ? 'bg-emerald-500' : 'bg-amber-500'
                      } shadow-[0_0_8px_rgba(16,185,129,0.4)]`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* AI Active Workers Card */}
        <div className="p-5 rounded-2xl bg-slate-900/50 border border-slate-800/50 backdrop-blur-xl group hover:border-cyan-500/30 transition-all duration-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <h3 className="font-semibold text-slate-200">Agent Telemetry</h3>
          </div>
          
          <div className="flex items-end gap-2 mb-2">
            <span className="text-4xl font-bold text-white tracking-tight">
              {healing.githubRuns.filter(r => r.status === 'in_progress').length + (healing.events.length > 0 ? 1 : 0)}
            </span>
            <span className="text-cyan-400 text-xs font-bold uppercase mb-1.5 animate-pulse">
              Active Workers
            </span>
          </div>
          <p className="text-xs text-slate-400 leading-relaxed">
            AI instances monitoring TAB4Racing and executing plan transformations.
          </p>
        </div>
      </div>

      {/* Healing Activity Log */}
      <div className="space-y-4">
        <div className="flex items-center gap-3 px-1">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-bold text-slate-200 uppercase tracking-widest">Healing Log</h3>
        </div>
        
        <div className="space-y-3">
          {healing.events.length === 0 && (
            <div className="p-8 text-center rounded-2xl border border-dashed border-slate-800 text-slate-500 text-sm">
              Waiting for agent activity...
            </div>
          )}
          {healing.events.slice().reverse().map((event, idx) => (
            <motion.div
              key={event.id}
              initial={{ x: -20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: idx * 0.1 }}
              className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/50 flex gap-4 items-start group hover:bg-slate-800/30 transition-all"
            >
              <div className={`mt-1 p-1.5 rounded-lg ${
                event.action === 'SELECTOR_HEALED' ? 'bg-emerald-500/10 text-emerald-400' : 
                event.action === 'PR_OPENED' ? 'bg-cyan-500/10 text-cyan-400' : 'bg-slate-500/10 text-slate-400'
              }`}>
                {event.action === 'PR_OPENED' ? <GitBranch className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-bold text-white group-hover:text-emerald-400 transition-colors uppercase tracking-wider">
                    {event.action.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-slate-400 leading-relaxed truncate group-hover:text-slate-300">
                  {event.details}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[10px] bg-slate-800 px-2 py-0.5 rounded text-slate-400 font-medium">
                    {event.agent}
                  </span>
                  <span className="text-[10px] text-emerald-500/80 font-bold uppercase tracking-tighter">
                    {event.status}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </motion.div>
  );
};
