import { useState, useEffect, useRef } from 'react';
import type { HUDState } from '../types';

export function useHUD() {
  const [state, setState] = useState<HUDState>({
    events: {},
    bankroll: null,
    learning: null,
    systemHealth: { cpu: 0, memory: 0, latency: 0, status: 'OFFLINE' },
    lastUpdate: Date.now()
  });

  const lastSnapshotHash = useRef<string | null>(null);

  useEffect(() => {
    const sync = async () => {
      try {
        const [snapshotRes, healthRes, bankrollRes] = await Promise.all([
          fetch('/api/monitoring/snapshot'),
          fetch('/api/system/health'),
          fetch('/api/betting/account-summary')
        ]);

        if (!snapshotRes.ok || !healthRes.ok) throw new Error('Backend link severed');
        
        const snapshot = await snapshotRes.json();
        const health = await healthRes.json();
        const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
        
        // Skip state update if snapshot hasn't changed (Differential Sync)
        if (snapshot.snapshot_hash === lastSnapshotHash.current) {
          // Just update health periodically
          setState(prev => ({
            ...prev,
            systemHealth: {
              cpu: health.cpu_usage_percent,
              memory: health.memory_usage_percent,
              latency: prev.systemHealth.latency,
              status: 'ONLINE'
            }
          }));
          return;
        }

        lastSnapshotHash.current = snapshot.snapshot_hash;

        const betsRes = await fetch('/api/betting/open');
        const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };
        
        setState(prev => ({
          ...prev,
          events: snapshot.events || {},
          bankroll: bankroll ? {
            balance: bankroll.balance,
            dailyLimit: bankroll.daily_limit,
            dailyLoss: bankroll.daily_loss,
            maxStake: bankroll.max_stake,
            totalExposure: bankroll.total_exposure || openBets.bets.reduce((acc: any, b: any) => acc + (b.stake || 0), 0)
          } : prev.bankroll,
          systemHealth: {
            cpu: health.cpu_usage_percent,
            memory: health.memory_usage_percent,
            latency: 0,
            status: 'ONLINE'
          },
          lastUpdate: Date.now()
        }));
      } catch (e) {
        setState(prev => ({
          ...prev,
          systemHealth: { ...prev.systemHealth, status: 'OFFLINE' }
        }));
      }
    };

    sync();
    const interval = setInterval(sync, 5000);
    return () => clearInterval(interval);
  }, []);

  return state;
}
