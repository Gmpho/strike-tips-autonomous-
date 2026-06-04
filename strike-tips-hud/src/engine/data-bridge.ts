import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playSettleTone } from './audio';
import { apiFetch } from '../lib/api-fetch';

const FAST_INTERVAL = 5000;
const SLOW_INTERVAL = 30000;
const MAX_FAST_BACKOFF = 60000;
const MAX_SLOW_BACKOFF = 120000;

export class DataBridge {
  private fastTimer: number | null = null;
  private slowTimer: number | null = null;
  private prevEventCount = 0;
  private prevBetCount = 0;
  private fastBackoffMs = FAST_INTERVAL;
  private slowBackoffMs = SLOW_INTERVAL;
  private refCount = 0;

  start() {
    this.refCount++;
    if (this.refCount > 1) return;
    this.scheduleFast();
    this.scheduleSlow();
  }

  stop() {
    this.refCount--;
    if (this.refCount > 0) return;
    if (this.fastTimer) clearTimeout(this.fastTimer);
    if (this.slowTimer) clearTimeout(this.slowTimer);
    this.fastTimer = null;
    this.slowTimer = null;
  }

  private scheduleFast() {
    this.fastTimer = window.setTimeout(() => this.runFast(), this.fastBackoffMs);
  }

  private scheduleSlow() {
    this.slowTimer = window.setTimeout(() => this.runSlow(), this.slowBackoffMs);
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

  private async runFast() {
    const start = performance.now();
    try {
      const [snapshotRes, healthRes, bankrollRes, betsRes] = await Promise.all([
        apiFetch('/api/monitoring/snapshot'),
        apiFetch('/api/system/health'),
        apiFetch(BETTING_ENDPOINTS.accountSummary),
        apiFetch(BETTING_ENDPOINTS.open),
      ]);

      if (!snapshotRes.ok || !healthRes.ok) throw new Error('Backend link severed');

      const snapshot = await snapshotRes.json();
      const health = await healthRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };

      const latency = performance.now() - start;

      hudStore.updateState({
        events: snapshot.events || {},
        alerts: snapshot.alerts || [],
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

      this.fastBackoffMs = FAST_INTERVAL;
    } catch {
      hudStore.updateState({
        systemHealth: {
          ...hudStore.getState().systemHealth,
          status: 'OFFLINE',
          latency: 0,
        },
      });
      this.fastBackoffMs = Math.min(this.fastBackoffMs * 2, MAX_FAST_BACKOFF);
    } finally {
      this.scheduleFast();
    }
  }

  private async runSlow() {
    try {
      const [historyRes, statsRes, roiRes, logsRes, healingRes, selectorsRes, vitalsRes, bankrollHistRes, memoryRes, moversRes, predRes, resultsRes] = await Promise.all([
        apiFetch(BETTING_ENDPOINTS.history),
        apiFetch(BETTING_ENDPOINTS.stats),
        apiFetch('/api/betting/learning/roi-by-track'),
        apiFetch('/api/logs?tail=100'),
        apiFetch('/api/healing/activity'),
        apiFetch('/api/healing/selectors'),
        apiFetch('/api/system/vitals'),
        apiFetch('/api/betting/bankroll-history'),
        apiFetch('/api/agent/memory'),
        apiFetch('/api/racing/market-movers'),
        apiFetch('/api/racing/predictor'),
        apiFetch('/api/racing/results'),
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
        marketMovers: moversRes.ok ? await moversRes.json() : [],
        predictions: predRes.ok ? await predRes.json() : [],
        results: resultsRes.ok ? await resultsRes.json() : [],
      });

      this.slowBackoffMs = SLOW_INTERVAL;
    } catch {
      this.slowBackoffMs = Math.min(this.slowBackoffMs * 2, MAX_SLOW_BACKOFF);
    } finally {
      this.scheduleSlow();
    }
  }
}

export const dataBridge = new DataBridge();
