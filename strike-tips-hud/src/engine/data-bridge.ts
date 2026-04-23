import { hudStore } from '../store/hud-store';
import type { VisualEngine } from './visual-engine';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';

export class DataBridge {
  private interval: number | null = null;
  private engine: VisualEngine | null = null;

  setEngine(engine: VisualEngine) {
    this.engine = engine;
  }

  start() {
    this.sync();
    // Fast cycle for real-time intelligence
    this.interval = window.setInterval(() => this.sync(), 5000);
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
  }

  private async sync() {
    const start = performance.now();
    try {
      // Parallel fetch for speed
      const [snapshotRes, bankrollRes] = await Promise.all([
        fetch('/api/monitoring/snapshot'),
        fetch(BETTING_ENDPOINTS.accountSummary)
      ]);

      if (!snapshotRes.ok) throw new Error('Backend link severed');
      
      const snapshot = await snapshotRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      
      const latency = performance.now() - start;

      hudStore.updateState({
        events: snapshot.events || {},
        bankroll: bankroll ? {
          balance: bankroll.balance,
          dailyLimit: bankroll.daily_limit,
          dailyLoss: bankroll.daily_loss,
          maxStake: bankroll.max_stake,
          totalExposure: bankroll.total_exposure || 0
        } : hudStore.getState().bankroll,
        systemHealth: {
          cpu: snapshot.system_health?.cpu || 0,
          memory: snapshot.system_health?.memory || 0,
          latency: Math.round(latency),
          status: 'ONLINE'
        }
      });
      this.engine?.updateData(snapshot.events || {});
    } catch (e) {
      hudStore.updateState({
        systemHealth: {
          ...hudStore.getState().systemHealth,
          status: 'OFFLINE',
          latency: 0
        }
      });
      this.loadMockData();
    }
  }

  private loadMockData() {
    if (Object.keys(hudStore.getState().events).length === 0) {
      hudStore.updateState({
        events: {
          "1": { 
            id: "1", 
            course: "TURFFONTEIN", 
            t: "14:10", 
            raceNumber: "4", 
            complexity: 'LOW_RISK',
            runners: [{name: "SILVER OPERA", odds: 4.5, form: "1-224", edge: 8.2}] 
          },
          "2": { 
            id: "2", 
            course: "GREYVILLE", 
            t: "15:45", 
            raceNumber: "7", 
            complexity: 'MEDIUM_RISK',
            runners: [{name: "PURPLE CLOUD", odds: 2.1, form: "31-15", edge: 5.4}] 
          }
        },
        bankroll: {
          balance: 2500.50,
          dailyLimit: 500,
          dailyLoss: 45.20,
          maxStake: 125.00,
          totalExposure: 85.00
        }
      });
    }
  }
}

export const dataBridge = new DataBridge();
