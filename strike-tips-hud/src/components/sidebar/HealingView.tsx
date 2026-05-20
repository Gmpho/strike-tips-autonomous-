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
          <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
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
        <div className="p-5 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-emerald-500/30 transition-all duration-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-emerald-500/10 text-emerald-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
            <h3 className="font-black text-theme-primary uppercase tracking-tight">Adaptive Selectors</h3>
          </div>
          
          <div className="space-y-4">
            {Object.entries(healing.selectors).slice(0, 3).map(([field, selectors]) => {
              const bestSelector = Object.entries(selectors)[0];
              const successRate = parseFloat(bestSelector[1].success_rate);
              return (
                <div key={field} className="space-y-1.5">
                  <div className="flex justify-between text-[10px]">
                    <span className="text-theme-secondary capitalize font-black tracking-tight">{field.replace('_', ' ')}</span>
                    <span className={successRate > 90 ? 'text-emerald-400 font-black' : 'text-amber-400 font-black'}>
                      {bestSelector[1].success_rate}
                    </span>
                  </div>
                  <div className="h-2 w-full bg-theme-secondary rounded-full overflow-hidden border border-theme/50">
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
        <div className="p-5 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl group hover:border-cyan-500/30 transition-all duration-500">
          <div className="flex items-center gap-3 mb-6">
            <div className="p-2 rounded-lg bg-cyan-500/10 text-cyan-400">
              <Activity className="w-5 h-5" />
            </div>
            <h3 className="font-black text-theme-primary uppercase tracking-tight">Agent Telemetry</h3>
          </div>
          
          <div className="flex items-end gap-2 mb-2">
            <span className="text-4xl font-black text-theme-primary tracking-tighter">
              {new Set([
                ...healing.githubRuns.filter((r: any) => r.status === 'in_progress').map(() => 'github'),
                ...(healing.events.some((e: any) => e.agent === 'OddsMonitor') ? ['OddsMonitor'] : []),
                ...(healing.events.some((e: any) => e.agent === 'AlertEngine') ? ['AlertEngine'] : []),
              ]).size || 1}
            </span>
            <span className="text-cyan-400 text-xs font-bold uppercase mb-1.5 animate-pulse">
              Active Workers
            </span>
          </div>
          <p className="text-[11px] text-theme-secondary leading-relaxed font-bold">
            AI instances monitoring TAB4Racing and executing plan transformations.
          </p>
        </div>
      </div>

      {/* Healing Activity Log */}
      <div className="space-y-4">
        <div className="flex items-center gap-3 px-1">
          <Terminal className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest">Healing Log</h3>
        </div>
        
        <div className="space-y-3">
          {healing.events.length === 0 && (
            <div className="p-8 text-center rounded-2xl border border-dashed border-theme text-theme-secondary text-sm font-bold">
              Waiting for agent activity...
            </div>
          )}
          {healing.events.slice().reverse().map((event, idx) => (
            <motion.div
              key={event.id}
              initial={{ x: -20, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              transition={{ delay: idx * 0.1 }}
              className="p-4 rounded-xl bg-theme-panel border border-theme flex gap-4 items-start group hover:bg-theme-secondary transition-all"
            >
              <div className={`mt-1 p-1.5 rounded-lg ${
                event.action === 'SELECTOR_HEALED' ? 'bg-emerald-500/10 text-emerald-400' : 
                event.action === 'PR_OPENED' ? 'bg-cyan-500/10 text-cyan-400' : 'bg-slate-500/10 text-slate-400'
              }`}>
                {event.action === 'PR_OPENED' ? <GitBranch className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-black text-theme-primary group-hover:text-emerald-400 transition-colors uppercase tracking-wider">
                    {event.action.replace('_', ' ')}
                  </span>
                  <span className="text-[10px] text-theme-secondary font-black tabular">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <p className="text-sm text-theme-secondary font-medium leading-relaxed truncate group-hover:text-theme-primary">
                  {event.details}
                </p>
                <div className="mt-2 flex items-center gap-2">
                  <span className="text-[10px] bg-theme-secondary px-2 py-0.5 rounded text-theme-secondary font-black border border-theme">
                    {event.agent}
                  </span>
                  <span className="text-[10px] text-emerald-500 font-black uppercase tracking-tighter">
                    {event.status}
                  </span>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
      {/* GitHub Workflow Runs */}
      {healing.githubRuns.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center gap-3 px-1">
            <GitBranch className="w-4 h-4 text-cyan-400" />
            <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest">GitHub Actions</h3>
          </div>
          <div className="space-y-3">
            {healing.githubRuns.slice(0, 5).map((run: any, idx: number) => (
              <motion.a
                key={run.id}
                href={run.url}
                target="_blank"
                rel="noopener noreferrer"
                initial={{ x: -20, opacity: 0 }}
                animate={{ x: 0, opacity: 1 }}
                transition={{ delay: idx * 0.1 }}
                className="p-4 rounded-xl bg-theme-panel border border-theme flex gap-4 items-start group hover:bg-theme-secondary transition-all cursor-pointer"
              >
                <div className={`mt-1 p-1.5 rounded-lg ${run.conclusion === 'success' ? 'bg-emerald-500/10 text-emerald-400' : run.status === 'in_progress' ? 'bg-cyan-500/10 text-cyan-400 animate-pulse' : 'bg-red-500/10 text-red-400'}`}>
                  <GitBranch className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs font-black text-theme-primary group-hover:text-cyan-400 transition-colors uppercase tracking-wider truncate">
                      {run.name || 'Workflow Run'}
                    </span>
                    <span className="text-[10px] text-theme-secondary font-black tabular ml-2 shrink-0">
                      {new Date(run.createdAt).toLocaleTimeString()}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-2">
                    <span className={`text-[10px] font-black uppercase tracking-tighter ${run.conclusion === 'success' ? 'text-emerald-500' : run.status === 'in_progress' ? 'text-cyan-400' : 'text-red-400'}`}>
                      {run.status === 'in_progress' ? 'RUNNING' : run.conclusion?.toUpperCase() || run.status?.toUpperCase()}
                    </span>
                    <span className="text-[10px] text-theme-secondary">GitHub Actions</span>
                  </div>
                </div>
              </motion.a>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
};
