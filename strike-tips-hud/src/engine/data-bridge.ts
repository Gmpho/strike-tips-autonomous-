import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playValueBetTone, playSettleTone } from './audio';

export class DataBridge {
  private interval: number | null = null;
  private prevEventCount = 0;
  private prevBetCount = 0;

  start() {
    this.sync();
    this.interval = window.setInterval(() => this.sync(), 5000);
  }

  stop() {
    if (this.interval) clearInterval(this.interval);
  }

  private playSoundsForChanges(snapshot: any, bankroll: any, history: any) {
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

  private async sync() {
    const start = performance.now();
    try {
      // Parallel fetch for speed
      const [snapshotRes, healthRes, bankrollRes, betsRes, historyRes, statsRes, roiRes, logsRes, healingRes, selectorsRes, vitalsRes, bankrollHistRes, memoryRes] = await Promise.all([
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
        fetch('/api/system/vitals'),
        fetch('/api/betting/bankroll-history'),
        fetch('/api/agent/memory')
      ]);

      if (!snapshotRes.ok || !healthRes.ok) throw new Error('Backend link severed');
      
      const snapshot = await snapshotRes.json();
      const health = await healthRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };
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
      
      const latency = performance.now() - start;

      this.playSoundsForChanges(snapshot, bankroll, history);

      hudStore.updateState({
        events: snapshot.events || {},
        betHistory: history.bets || [],
        betStats: stats,
        logs: logs.logs || [],
        learning: {
          totalRoi: stats?.roi || 0,
          samples: stats?.totalBets || 0,
          topTrack: Object.entries(roiByTrack).sort((a: any, b: any) => b[1] - a[1])[0]?.[0] || 'N/A',
          accuracy: roiAccuracy,
          roiByTrack: roiByTrack
        },
        bankrollHistory: bankrollHist.history || [],
        honcho: memoryData ? {
          status: memoryData.status || 'no_data_yet',
          context: memoryData.context || '',
          dreamContext: memoryData.dream_context || '',
        } : null,
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
