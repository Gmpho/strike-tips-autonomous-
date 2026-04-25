import React from 'react';
import { motion } from 'framer-motion';
import { Cpu, HardDrive, Network, Server } from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';

export const SystemVitalsView: React.FC = () => {
  const { systemHealth, vitals } = useHUD();

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="p-6 space-y-8"
    >
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold bg-linear-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">
          Intelligence Vitals
        </h2>
        <p className="text-xs text-theme-secondary mt-1 uppercase tracking-widest font-black">
          Agent Performance & Reasoning Efficiency
        </p>
      </div>

      {/* Bare Metal Stats */}
      <div className="grid grid-cols-3 gap-4">
        {[
          { label: 'CPU LOAD', value: `${systemHealth.cpu}%`, icon: Cpu, color: 'text-blue-500' },
          { label: 'MEMORY', value: `${systemHealth.memory}%`, icon: HardDrive, color: 'text-indigo-500' },
          { label: 'LATENCY', value: `${systemHealth.latency}ms`, icon: Network, color: 'text-cyan-500' },
        ].map((stat, i) => (
          <div key={i} className="p-4 rounded-2xl bg-theme-panel border border-theme backdrop-blur-xl">
            <stat.icon className={`w-4 h-4 ${stat.color} mb-3`} />
            <div className="text-xl font-black text-theme-primary mb-0.5 tabular">{stat.value}</div>
            <div className="text-[10px] text-theme-secondary font-black tracking-tighter uppercase">{stat.label}</div>
          </div>
        ))}
      </div>

      {/* Docker Containers Section */}
      <div className="space-y-4">
        <div className="flex items-center gap-3 px-1">
          <Server className="w-4 h-4 text-blue-500" />
          <h3 className="text-sm font-black text-theme-primary uppercase tracking-widest">Intelligence Engine</h3>
        </div>

        <div className="space-y-4">
          {vitals.docker.length === 0 && (
            <div className="p-8 text-center rounded-2xl border border-dashed border-theme text-theme-secondary text-sm font-bold">
              Waiting for docker telemetry...
            </div>
          )}
          {vitals.docker.map((container, idx) => (
            <motion.div
              key={container.id}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.1 }}
              className="p-5 rounded-2xl bg-theme-panel border border-theme group hover:border-blue-500/30 transition-all duration-500"
            >
              <div className="flex items-center justify-between mb-6">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-lg bg-blue-500/10 text-blue-400 group-hover:scale-110 transition-transform">
                    <Server className="w-4 h-4" />
                  </div>
                  <div>
                    <div className="text-sm font-black text-theme-primary tracking-wide uppercase">{container.name}</div>
                    <div className="text-[10px] text-theme-secondary font-black tabular">ID: {container.id.slice(0, 12)}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
                  <span className="text-[10px] font-bold text-emerald-500 uppercase tracking-tighter">Running</span>
                </div>
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div className="space-y-2">
                  <div className="flex justify-between text-[10px] font-black tracking-wider text-theme-secondary uppercase">
                    <span>{container.id.startsWith('ai-') ? 'Success Rate' : 'CPU Usage'}</span>
                    <span className="text-blue-500 font-black">{container.cpu || '0%'}</span>
                  </div>
                  <div className="h-1.5 w-full bg-theme-secondary rounded-full overflow-hidden border border-theme/50">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: container.cpu || '0%' }}
                      className="h-full bg-blue-500 shadow-[0_0_8px_rgba(59,130,246,0.4)]"
                    />
                  </div>
                </div>
                <div className="space-y-2">
                  <div className="flex justify-between text-[10px] font-black tracking-wider text-theme-secondary uppercase">
                    <span>{container.id.startsWith('ai-') ? 'Latency' : 'Memory'}</span>
                    <span className="text-indigo-500 font-black">{container.mem || '0%'}</span>
                  </div>
                  <div className="h-1.5 w-full bg-theme-secondary rounded-full overflow-hidden border border-theme/50">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: container.mem || '0%' }}
                      className="h-full bg-indigo-500 shadow-[0_0_8px_rgba(99,102,241,0.4)]"
                    />
                  </div>
                  <div className="text-[9px] text-theme-secondary font-black tabular truncate">
                    {container.mem_usage}
                  </div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>

      {/* Cooling System / Battery Optimization Note */}
      <div className="p-4 rounded-xl bg-amber-500/5 border border-amber-500/10 text-center">
        <p className="text-[10px] text-amber-500/70 font-medium leading-relaxed italic">
          "Bare Metal Battery Protection active. Dynamic framerate throttling engaged for background R3F layers."
        </p>
      </div>
    </motion.div>
  );
};
