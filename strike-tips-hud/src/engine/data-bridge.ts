import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playSettleTone } from './audio';

const FAST_INTERVAL = 5000;
const SLOW_INTERVAL = 30000;

export class DataBridge {
  private fastInterval: number | null = null;
  private slowInterval: number | null = null;
  private prevEventCount = 0;
  private prevBetCount = 0;

  start() {
    this.syncFast();
    this.syncSlow();
    this.fastInterval = window.setInterval(() => this.syncFast(), FAST_INTERVAL);
    this.slowInterval = window.setInterval(() => this.syncSlow(), SLOW_INTERVAL);
  }

  stop() {
    if (this.fastInterval) clearInterval(this.fastInterval);
    if (this.slowInterval) clearInterval(this.slowInterval);
  }

  private playSoundsForChanges(snapshot: any, _bankroll: any, history: any) {
    const eventCount = Object.keys(snapshot.events || {}).length;
    if (eventCount > this.prevEventCount && this.prevEventCount > 0) {
      playAlertTone();
    }
    this.prevEventCount = eventCount;

    const bets = history.bets || [];
    const settledCount = bets.filter((b: any) => b.settled).length;
    const prevSettled = this.prevBetCount;
    if (settledCount > prevSettled && prevSettled > 0) {
      const newSettled = bets.filter((b: any) => b.settled);
      const won = newSettled[newSettled.length - 1]?.won ?? false;
      playSettleTone(won);
    }
    this.prevBetCount = settledCount;
  }

  private async syncFast() {
    const start = performance.now();
    try {
      const [snapshotRes, healthRes, bankrollRes, betsRes] = await Promise.all([
        fetch('/api/monitoring/snapshot'),
        fetch('/api/system/health'),
        fetch(BETTING_ENDPOINTS.accountSummary),
        fetch(BETTING_ENDPOINTS.open),
      ]);

      if (!snapshotRes.ok || !healthRes.ok) throw new Error('Backend link severed');

      const snapshot = await snapshotRes.json();
      const health = await healthRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };

      const latency = performance.now() - start;

      hudStore.updateState({
        events: snapshot.events || {},
        systemHealth: {
          cpu: health.cpu_usage_percent || 0,
          memory: health.memory_usage_percent || 0,
          latency: Math.round(latency),
          status: 'ONLINE',
        },
        bankroll: bankroll ? {
          balance: bankroll.balance,
          dailyLimit: bankroll.dailyLimit || bankroll.daily_limit,
          dailyLoss: bankroll.dailyLoss || bankroll.daily_loss,
          maxStake: bankroll.maxStake || bankroll.max_stake,
          totalExposure: bankroll.totalExposure || bankroll.total_exposure || openBets.bets?.reduce((acc: any, b: any) => acc + (b.stake || 0), 0) || 0,
        } : hudStore.getState().bankroll,
      });

      this.playSoundsForChanges(snapshot, bankroll, { bets: hudStore.getState().betHistory });
    } catch {
      hudStore.updateState({
        systemHealth: {
          ...hudStore.getState().systemHealth,
          status: 'OFFLINE',
          latency: 0,
        },
      });
    }
  }

  private async syncSlow() {
    try {
      const [historyRes, statsRes, roiRes, logsRes, healingRes, selectorsRes, vitalsRes, bankrollHistRes, memoryRes] = await Promise.all([
        fetch(BETTING_ENDPOINTS.history),
        fetch(BETTING_ENDPOINTS.stats),
        fetch('/api/betting/learning/roi-by-track'),
        fetch('/api/logs?tail=100'),
        fetch('/api/healing/activity'),
        fetch('/api/healing/selectors'),
        fetch('/api/system/vitals'),
        fetch('/api/betting/bankroll-history'),
        fetch('/api/agent/memory'),
      ]);

      const history = historyRes.ok ? await historyRes.json() : { bets: [] };
      const stats = statsRes.ok ? await statsRes.json() : null;
      const roiRaw = roiRes.ok ? await roiRes.json() : {};
      const roiByTrack = roiRaw.roiByTrack ?? roiRaw;
      const roiAccuracy = roiRaw.accuracy ?? 0;
      const logs = logsRes.ok ? await logsRes.json() : { logs: [] };
      const healing = healingRes.ok ? await healingRes.json() : { internal_events: [], github_runs: [] };
      const selectors = selectorsRes.ok ? await selectorsRes.json() : { report: {} };
      const vitals = vitalsRes.ok ? await vitalsRes.json() : { vitals: [] };
      const bankrollHist = bankrollHistRes.ok ? await bankrollHistRes.json() : { history: [] };
      const memoryData = memoryRes.ok ? await memoryRes.json() : null;

      hudStore.updateState({
        betHistory: history.bets || [],
        betStats: stats,
        logs: logs.logs || [],
        learning: {
          totalRoi: stats?.roi || 0,
          samples: stats?.totalBets || 0,
          topTrack: Object.entries(roiByTrack).sort((a: any, b: any) => b[1] - a[1])[0]?.[0] || 'N/A',
          accuracy: roiAccuracy,
          roiByTrack,
        },
        bankrollHistory: bankrollHist.history || [],
        honcho: memoryData ? {
          status: memoryData.status || 'no_data_yet',
          context: memoryData.context || '',
          dreamContext: memoryData.dream_context || '',
        } : null,
        healing: {
          events: healing.internal_events || [],
          selectors: selectors.report || {},
          githubRuns: healing.github_runs || [],
        },
        vitals: {
          docker: vitals.vitals || [],
        },
      });
    } catch {
      // Silent — non-critical data, keep previous state
    }
  }
}

export const dataBridge = new DataBridge();
