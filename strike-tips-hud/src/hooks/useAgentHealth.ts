import { useEffect, useState } from 'react';

type HealthStatus = {
  orchestrator: string;
  ollama: string;
};

const POLL_INTERVAL_MS = 25000;

let healthState: HealthStatus = { orchestrator: 'pending', ollama: 'pending' };
let poller: number | null = null;
let inFlight: Promise<void> | null = null;
const listeners = new Set<(state: HealthStatus) => void>();

const notify = () => {
  listeners.forEach((listener) => listener(healthState));
};

const syncHealth = async () => {
  if (inFlight) {
    return inFlight;
  }

  inFlight = (async () => {
    try {
      const res = await fetch('/api/agent/health');
      const data = await res.json();
      const ollamaRaw = data.ollama ?? 'error';
      healthState = {
        orchestrator: data.orchestrator ?? 'error',
        ollama: ollamaRaw === 'error' ? 'offline' : ollamaRaw,
      };
    } catch {
      healthState = { orchestrator: 'error', ollama: 'offline' };
    } finally {
      notify();
      inFlight = null;
    }
  })();

  return inFlight;
};

const ensurePoller = () => {
  if (poller !== null) {
    return;
  }

  void syncHealth();
  poller = window.setInterval(() => {
    void syncHealth();
  }, POLL_INTERVAL_MS);
};

const cleanupPoller = () => {
  if (listeners.size > 0 || poller === null) {
    return;
  }

  window.clearInterval(poller);
  poller = null;
};

export const useAgentHealth = () => {
  const [health, setHealth] = useState<HealthStatus>(healthState);

  useEffect(() => {
    listeners.add(setHealth);
    ensurePoller();
    setHealth(healthState);

    return () => {
      listeners.delete(setHealth);
      cleanupPoller();
    };
  }, []);

  return {
    health,
    refreshHealth: syncHealth,
  };
};
