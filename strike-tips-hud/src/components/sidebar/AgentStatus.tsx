import React, { useState } from 'react';
import { Power, AlertTriangle, Cpu, Activity, Database, ShieldX } from 'lucide-react';
import { useAgentHealth } from '../../hooks/useAgentHealth';
import { motion } from 'framer-motion';
import { apiFetch } from '../../lib/api-fetch';

// The backend confirms each transition in-band:
//   POST /api/agent/kill  -> {"success":true,"message":"EMERGENCY STOP ACTIVATED","status":"locked"}
//   POST /api/agent/reset -> {"success":true,"message":"SYSTEM RESET COMPLETE","status":"active"}
// The UI may only reflect a state the server has confirmed: res.ok AND the
// body's status field must match. Anything else renders an error instead.
const EXPECTED_STATUS = { '/api/agent/kill': 'locked', '/api/agent/reset': 'active' } as const;

export const AgentStatus: React.FC = () => {
  const { health } = useAgentHealth();
  const [isLocked, setIsLocked] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggleLock = async () => {
    const endpoint = isLocked ? '/api/agent/reset' : '/api/agent/kill';
    const wanted = EXPECTED_STATUS[endpoint as keyof typeof EXPECTED_STATUS];
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch(endpoint, { method: 'POST' });
      if (!res.ok) {
        setError(`Emergency stop failed (HTTP ${res.status}) — agent state unchanged.`);
        return; // never flip on a failed call
      }
      let body: { success?: unknown; status?: unknown } = {};
      try {
        body = await res.json();
      } catch {
        setError('Emergency stop failed (unreadable response) — agent state unchanged.');
        return;
      }
      if (body.success !== true || body.status !== wanted) {
        setError(`Emergency stop failed (unexpected response) — agent state unchanged.`);
        return;
      }
      setIsLocked(wanted === 'locked');
    } catch {
      setError('Emergency stop failed (network error) — agent state unchanged.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <motion.div 
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-6 bg-theme-panel rounded-3xl border border-theme  mx-2 mb-6 hover:shadow-[0_0_30px_rgba(168,85,247,0.1)] transition-shadow"
    >
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Cpu className="w-4 h-4 text-purple-500" />
          <span className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">Agent Pipeline</span>
        </div>
        <button onClick={toggleLock} disabled={busy} aria-label={isLocked ? "Unlock agent pipeline" : "Lock agent pipeline"} aria-busy={busy} className="p-1.5 hover:bg-theme-secondary rounded-lg transition-colors border border-theme disabled:opacity-50 disabled:cursor-not-allowed">
          {isLocked ? <AlertTriangle className="w-4 h-4 text-red-500" /> : <Power className="w-4 h-4 text-emerald-500" />}
        </button>
      </div>
      {error && (
        <div role="alert" className="flex items-center gap-2 p-2.5 mb-4 rounded-xl bg-red-500/10 border border-red-500/20">
          <ShieldX className="w-4 h-4 text-red-400 shrink-0" />
          <span className="text-[11px] font-bold text-red-400 leading-snug">{error}</span>
        </div>
      )}
      
      <div className="space-y-4">
        <div className="flex items-center justify-between p-3 bg-theme-secondary rounded-xl border border-theme">
          <div className="flex items-center gap-3">
            <Activity className="w-4 h-4 text-theme-secondary" />
            <span className="text-xs font-bold text-theme-primary">Orchestrator</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.orchestrator === 'ready' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'}`}>
            {health.orchestrator}
          </span>
        </div>

        <div className="flex items-center justify-between p-3 bg-theme-secondary rounded-xl border border-theme">
          <div className="flex items-center gap-3">
            <Database className="w-4 h-4 text-theme-secondary" />
            <span className="text-xs font-bold text-theme-primary">Local Model (Ollama)</span>
          </div>
          <span className={`text-[10px] font-black uppercase tracking-widest px-2 py-1 rounded ${health.ollama === 'connected' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : health.ollama === 'no_models' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' : 'bg-slate-500/10 text-slate-400 border border-slate-500/20'}`}>
            {health.ollama === 'connected' ? 'CONNECTED' : health.ollama === 'no_models' ? 'NO MODELS' : 'OFFLINE'}
          </span>
        </div>
      </div>
    </motion.div>
  );
};
