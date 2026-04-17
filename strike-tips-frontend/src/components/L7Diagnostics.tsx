import React from 'react';
import { Activity, Cpu, HardDrive, Shield } from 'lucide-react';
import { L7Health } from '@/lib/api';

interface L7DiagnosticsProps {
  health: L7Health | null;
}

export function L7Diagnostics({ health }: L7DiagnosticsProps) {
  if (!health) return null;

  const isHealthy = health.status === 'HEALTHY';
  
  return (
    <div className="flex items-center gap-4 bg-white/5 border border-white/10 rounded-full px-4 py-2 mt-4 lg:mt-0">
      {/* Status Pulse */}
      <div className="flex items-center gap-2 pr-3 border-r border-white/10">
        <div className="relative flex h-3 w-3">
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${isHealthy ? 'bg-emerald-400' : 'bg-rose-400'}`}></span>
          <span className={`relative inline-flex rounded-full h-3 w-3 ${isHealthy ? 'bg-emerald-500' : 'bg-rose-500'}`}></span>
        </div>
        <span className="text-xs font-bold text-slate-300 uppercase tracking-widest">
          {health.status}
        </span>
      </div>

      {/* CPU */}
      <div className="flex items-center gap-1.5 text-slate-400">
        <Cpu className="w-3.5 h-3.5" />
        <span className="text-[11px] font-black tabular-nums">{health.cpu_usage_percent.toFixed(1)}%</span>
      </div>

      {/* Memory */}
      <div className="flex items-center gap-1.5 text-slate-400">
        <HardDrive className="w-3.5 h-3.5" />
        <span className="text-[11px] font-black tabular-nums">{health.memory_usage_percent.toFixed(1)}%</span>
      </div>

      {/* Stealth */}
      <div className="flex items-center gap-1.5 text-slate-400 pl-2 border-l border-white/10">
        <Shield className="w-3.5 h-3.5 text-indigo-400" />
        <span className="text-[11px] font-black tracking-wide text-indigo-300">STEALTH ON</span>
      </div>
    </div>
  );
}
