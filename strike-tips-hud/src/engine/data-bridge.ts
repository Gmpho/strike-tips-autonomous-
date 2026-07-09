import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playSettleTone, playValueBetTone } from './audio';
import { apiFetch } from '../lib/api-fetch';

const FAST_INTERVAL = 5000;
const SLOW_INTERVAL = 15000;
const MAX_FAST_BACKOFF = 60000;
const MAX_SLOW_BACKOFF = 120000;
const SSE_URL = '/api/monitoring/stream';

export class DataBridge {
  private fastTimer: number | null = null;
  private slowTimer: number | null = null;
  private sse: EventSource | null = null;
  private sseReconnectMs = 2000;
  private prevEventCount = 0;
  private prevBetCount = 0;
  private playedValueBets = new Set<string>();
  private fastBackoffMs = FAST_INTERVAL;
  private slowBackoffMs = SLOW_INTERVAL;
  private refCount = 0;

  start() {
    this.refCount++;
    if (this.refCount > 1) return;
    this.connectSSE();
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
    this.disconnectSSE();
  }

  private connectSSE() {
    this.disconnectSSE();
    this.sse = new EventSource(SSE_URL);

    this.sse.addEventListener('snapshot', (e: MessageEvent) => {
      try {
        const data = JSON.parse(e.data);
        const current = hudStore.getState();
        hudStore.updateState({
          events: data.events || {},
          alerts: data.alerts || [],
        });
        this.playSoundsForChanges(data, null, { bets: current.betHistory });
      } catch (err) {
        console.error('SSE snapshot parse error:', err);
      }
    });

    this.sse.addEventListener('market-movers', (e: MessageEvent) => {
      try {
        hudStore.updateState({ marketMovers: JSON.parse(e.data) });
      } catch (err) {
        console.error('SSE market-movers parse error:', err);
      }
    });

    this.sse.addEventListener('predictor', (e: MessageEvent) => {
      try {
        hudStore.updateState({ predictions: JSON.parse(e.data) });
      } catch (err) {
        console.error('SSE predictor parse error:', err);
      }
    });

    this.sse.addEventListener('results', (e: MessageEvent) => {
      try {
        hudStore.updateState({ results: JSON.parse(e.data) });
      } catch (err) {
        console.error('SSE results parse error:', err);
      }
    });

    this.sse.onerror = () => {
      this.disconnectSSE();
      setTimeout(() => this.connectSSE(), this.sseReconnectMs);
      this.sseReconnectMs = Math.min(this.sseReconnectMs * 2, 30000);
    };

    this.sse.onopen = () => {
      this.sseReconnectMs = 2000;
    };
  }

  private disconnectSSE() {
    if (this.sse) {
      this.sse.close();
      this.sse = null;
    }
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

    // Priority Edge Alerts logic
    try {
      const valueBetAlertsEnabled = localStorage.getItem('strike_value_bet_alerts') === 'true';
      if (valueBetAlertsEnabled) {
        // Iterate through all runners in all active events
        Object.values(snapshot.events || {}).forEach((event: any) => {
          const course = event.course || 'Unknown';
          const raceNum = event.raceNumber || '';
          (event.runners || []).forEach((runner: any) => {
            const edge = runner.edge;
            // Check if edge is greater than or equal to 15%
            if (edge && edge >= 15) {
              const key = `${course}_${raceNum}_${runner.name}`;
              if (!this.playedValueBets.has(key)) {
                this.playedValueBets.add(key);
                playValueBetTone();
              }
            }
          });
        });
      }
    } catch (e) {
      console.error('Error processing priority edge alerts sound:', e);
    }
  }

  private async runFast() {
    const start = performance.now();
    try {
      const [healthRes, bankrollRes, betsRes] = await Promise.all([
        apiFetch('/api/system/health'),
        apiFetch(BETTING_ENDPOINTS.accountSummary),
        apiFetch(BETTING_ENDPOINTS.open),
      ]);

      if (!healthRes.ok) throw new Error('Backend link severed');

      const health = await healthRes.json();
      const bankroll = bankrollRes.ok ? await bankrollRes.json() : null;
      const openBets = betsRes.ok ? await betsRes.json() : { bets: [] };

      const latency = performance.now() - start;
      const current = hudStore.getState();

      hudStore.updateState({
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
        } : current.bankroll,
      });

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
      const [historyRes, statsRes, roiRes, logsRes, healingRes, selectorsRes, vitalsRes, bankrollHistRes, memoryRes] = await Promise.all([
        apiFetch(BETTING_ENDPOINTS.history),
        apiFetch(BETTING_ENDPOINTS.stats),
        apiFetch('/api/betting/learning/roi-by-track'),
        apiFetch('/api/logs?tail=100'),
        apiFetch('/api/healing/activity'),
        apiFetch('/api/healing/selectors'),
        apiFetch('/api/system/vitals'),
        apiFetch('/api/betting/bankroll-history'),
        apiFetch('/api/agent/memory'),
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

      this.slowBackoffMs = SLOW_INTERVAL;
    } catch {
      this.slowBackoffMs = Math.min(this.slowBackoffMs * 2, MAX_SLOW_BACKOFF);
    } finally {
      this.scheduleSlow();
    }
  }
}

export const dataBridge = new DataBridge();
