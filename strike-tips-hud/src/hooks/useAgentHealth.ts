import { useEffect, useState } from 'react';
import { apiFetch } from '../lib/api-fetch';

type HealthStatus = {
  orchestrator: string;
  ollama: string;
};

const POLL_INTERVAL_MS = 25000;
const MAX_BACKOFF_MS = 120000;

let healthState: HealthStatus = { orchestrator: 'pending', ollama: 'pending' };
let pollTimer: number | null = null;
let backoffMs = POLL_INTERVAL_MS;
let inFlight: Promise<void> | null = null;
const listeners = new Set<(state: HealthStatus) => void>();

const notify = () => {
  listeners.forEach((listener) => listener(healthState));
};

const syncHealth = async () => {
  if (inFlight) return inFlight;

  inFlight = (async () => {
    try {
      const res = await apiFetch('/v1/health');
      const data = await res.json();
      healthState = {
        orchestrator: data.orchestrator ?? 'ready',
        ollama: data.ollama ?? 'offline',
      };
      backoffMs = POLL_INTERVAL_MS;
    } catch {
      healthState = { orchestrator: 'error', ollama: 'offline' };
      backoffMs = Math.min(backoffMs * 2, MAX_BACKOFF_MS);
    } finally {
      notify();
      inFlight = null;
    }
  })();

  return inFlight;
};

const scheduleNext = () => {
  if (pollTimer !== null) clearTimeout(pollTimer);
  pollTimer = window.setTimeout(() => {
    syncHealth().finally(scheduleNext);
  }, backoffMs);
};

const startPoller = () => {
  syncHealth().finally(scheduleNext);
};

const stopPoller = () => {
  if (pollTimer !== null) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

export const useAgentHealth = () => {
  const [health, setHealth] = useState<HealthStatus>(healthState);

  useEffect(() => {
    listeners.add(setHealth);
    if (pollTimer === null) startPoller();
    setHealth(healthState);

    return () => {
      listeners.delete(setHealth);
      if (listeners.size === 0) stopPoller();
    };
  }, []);

  return {
    health,
    refreshHealth: syncHealth,
  };
};