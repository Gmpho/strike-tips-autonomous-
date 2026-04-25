import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';

export class DataBridge {
  private interval: number | null = null;

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
      const [snapshotRes, healthRes, bankrollRes, betsRes, historyRes, statsRes, roiRes, logsRes, healingRes, selectorsRes, vitalsRes] = await Promise.all([
        fetch('/api/monitoring/snapshot'),
        fetch('/api/system/health'),
        fetch(BETTING_ENDPOINTS.accountSummary),
        fetch(BETTING_ENDPOINTS.open),
        fetch(BETTING_ENDPOINTS.history),
        fetch(BETTING_ENDPOINTS.stats),
        fetch('/api/betting/learning/roi-by-track'),
        fetch('/api/logs?tail=100'),
        fetch('/api/healing/activity'),
        fetch('/api/healing/selectors'),
        fetch('/api/system/vitals')
      ]);

      if (!snapshotRes.ok || !healthRes.ok) throw new Error('Backend link severed');
      
      const snapshot = await snapshotRes.json();
      const health = await healthRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };
      const history = historyRes.ok ? await historyRes.json() : { bets: [] };
      const stats = statsRes.ok ? await statsRes.json() : null;
      const roiByTrack = roiRes.ok ? await roiRes.json() : {};
      const logs = logsRes.ok ? await logsRes.json() : { logs: [] };
      const healing = healingRes.ok ? await healingRes.json() : { internal_events: [], github_runs: [] };
      const selectors = selectorsRes.ok ? await selectorsRes.json() : { report: {} };
      const vitals = vitalsRes.ok ? await vitalsRes.json() : { vitals: [] };
      
      const latency = performance.now() - start;

      hudStore.updateState({
        events: snapshot.events || {},
        betHistory: history.bets || [],
        betStats: stats,
        logs: logs.logs || [],
        learning: {
          totalRoi: stats?.roi || 0,
          samples: stats?.totalBets || 0,
          topTrack: Object.entries(roiByTrack).sort((a: any, b: any) => b[1] - a[1])[0]?.[0] || 'N/A',
          accuracy: 0,
          roiByTrack: roiByTrack
        },
        bankroll: bankroll ? {
          balance: bankroll.balance,
          dailyLimit: bankroll.dailyLimit || bankroll.daily_limit,
          dailyLoss: bankroll.dailyLoss || bankroll.daily_loss,
          maxStake: bankroll.maxStake || bankroll.max_stake,
          totalExposure: bankroll.totalExposure || bankroll.total_exposure || openBets.bets?.reduce((acc: any, b: any) => acc + (b.stake || 0), 0) || 0
        } : hudStore.getState().bankroll,
        systemHealth: {
          cpu: health.cpu_usage_percent || 0,
          memory: health.memory_usage_percent || 0,
          latency: Math.round(latency),
          status: 'ONLINE'
        },
        healing: {
          events: healing.internal_events || [],
          selectors: selectors.report || {},
          githubRuns: healing.github_runs || []
        },
        vitals: {
          docker: vitals.vitals || []
        }
      });
    } catch (e) {
      hudStore.updateState({
        systemHealth: {
          ...hudStore.getState().systemHealth,
          status: 'OFFLINE',
          latency: 0
        }
      });
      // Do NOT load mock data. Keep whatever state we had previously so UI doesn't hardcode flash.
    }
  }

}

export const dataBridge = new DataBridge();
