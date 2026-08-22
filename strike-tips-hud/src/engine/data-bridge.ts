import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playSettleTone, playValueBetTone } from './audio';
import { apiFetch } from '../lib/api-fetch';

const FAST_INTERVAL = 5000;
const SLOW_INTERVAL = 15000;
const MAX_FAST_BACKOFF = 60000;
const MAX_SLOW_BACKOFF = 120000;
// Connect directly to the Modal SSE origin to bypass the Vercel Edge middleware
// runtime cap (~300s). /api/monitoring/stream is in SAFE_PATHS (no API key needed)
// and the backend CORS allows the production origin.
const SSE_ORIGIN = 'https://gmpho--strike-tips-racing-serve-api.modal.run';
const SSE_URL = `${SSE_ORIGIN}/api/monitoring/stream`;

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
    this.hydrateFeeds();
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

    this.sse.addEventListener('news', (e: MessageEvent) => {
      try {
        const items = JSON.parse(e.data);
        if (Array.isArray(items)) hudStore.updateState({ news: items });
      } catch (err) {
        console.error('SSE news parse error:', err);
      }
    });

    this.sse.addEventListener('telemetry', (e: MessageEvent) => {
      try {
        const fresh = JSON.parse(e.data) as Array<{ engine: string; badge: string; message: string; ts: number }>;
        if (!Array.isArray(fresh)) return;
        const existing = hudStore.getState().telemetry || [];
        const seen = new Set(existing.map(t => `${t.engine}|${t.message}|${t.ts}`));
        const merged = [...fresh.filter(t => !seen.has(`${t.engine}|${t.message}|${t.ts}`)), ...existing].slice(0, 30);
        hudStore.updateState({ telemetry: merged });
      } catch (err) {
        console.error('SSE telemetry parse error:', err);
      }
    });

    this.sse.addEventListener('news', (e: MessageEvent) => {
      try {
        const items = JSON.parse(e.data);
        if (Array.isArray(items)) {
          hudStore.updateState({ news: items });
        }
      } catch (err) {
        console.error('SSE news parse error:', err);
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

  /** One-shot REST hydration for news + telemetry before SSE events arrive. */
  private async hydrateFeeds() {
    await this.hydrateNews();
    try {
      const telRes = await apiFetch('/api/telemetry');
      if (telRes.ok) {
        const data = await telRes.json();
        if (Array.isArray(data.events)) hudStore.updateState({ telemetry: data.events.slice(0, 30) });
      }
    } catch (err) {
      console.error('Telemetry hydration failed:', err);
    }
  }

  async refreshNews() {
    await this.hydrateNews();
  }

  private async hydrateNews() {
    try {
      const res = await fetch('/api/news');
      if (res.ok) {
        const data = await res.json();
        if (Array.isArray(data.items) && data.items.length > 0) {
          hudStore.updateState({ news: data.items });
        }
      }
    } catch {
      // SSE news events cover this path when REST is unavailable
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
      const activeView = typeof localStorage !== 'undefined' ? localStorage.getItem('strike_active_view') : 'dashboard';

      const needStats = ['analytics', 'bankroll'].includes(activeView || '');
      const needHistory = ['bankroll', 'analytics'].includes(activeView || '');
      const needRoi = ['analytics'].includes(activeView || '');
      const needLogs = ['logs'].includes(activeView || '');
      const needHealing = ['healing'].includes(activeView || '');
      const needVitals = ['vitals'].includes(activeView || '');
      const needMemory = ['agents'].includes(activeView || '');

      const [historyRes, statsRes, roiRes, roiOddsRes, logsRes, healingRes, selectorsRes, vitalsRes, bankrollHistRes, memoryRes] = await Promise.all([
        needHistory ? apiFetch(BETTING_ENDPOINTS.history) : Promise.resolve(null),
        needStats ? apiFetch(BETTING_ENDPOINTS.stats) : Promise.resolve(null),
        needRoi ? apiFetch('/api/betting/learning/roi-by-track') : Promise.resolve(null),
        needRoi ? apiFetch('/api/betting/learning/roi-by-odds-range') : Promise.resolve(null),
        needLogs ? apiFetch('/api/logs?tail=100') : Promise.resolve(null),
        needHealing ? apiFetch('/api/healing/activity') : Promise.resolve(null),
        needHealing ? apiFetch('/api/healing/selectors') : Promise.resolve(null),
        needVitals ? apiFetch('/api/system/vitals') : Promise.resolve(null),
        needHistory || needRoi ? apiFetch('/api/betting/bankroll-history') : Promise.resolve(null),
        needMemory ? apiFetch('/api/agent/memory') : Promise.resolve(null),
      ]);

      const currentState = hudStore.getState();

      const history = (historyRes && historyRes.ok) ? await historyRes.json() : { bets: currentState.betHistory };
      const stats = (statsRes && statsRes.ok) ? await statsRes.json() : currentState.betStats;
      const roiRaw = (roiRes && roiRes.ok) ? await roiRes.json() : { roiByTrack: currentState.learning?.roiByTrack, accuracy: currentState.learning?.accuracy };
      const roiByTrack = roiRaw.roiByTrack ?? roiRaw;
      const roiAccuracy = roiRaw.accuracy ?? 0;
      const roiOdds = (roiOddsRes && roiOddsRes.ok) ? await roiOddsRes.json() : currentState.learning?.roiByOddsRange;
      const logs = (logsRes && logsRes.ok) ? await logsRes.json() : { logs: currentState.logs };
      const healing = (healingRes && healingRes.ok) ? await healingRes.json() : { internal_events: currentState.healing.events, github_runs: currentState.healing.githubRuns };
      const selectors = (selectorsRes && selectorsRes.ok) ? await selectorsRes.json() : { report: currentState.healing.selectors };
      const vitals = (vitalsRes && vitalsRes.ok) ? await vitalsRes.json() : { vitals: currentState.vitals.docker };
      const bankrollHist = (bankrollHistRes && bankrollHistRes.ok) ? await bankrollHistRes.json() : { history: currentState.bankrollHistory };
      const memoryData = (memoryRes && memoryRes.ok) ? await memoryRes.json() : null;

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
          roiByOddsRange: roiOdds,
        },
        bankrollHistory: bankrollHist.history || [],
        honcho: memoryData ? {
          status: memoryData.status || 'no_data_yet',
          context: memoryData.context || '',
          dreamContext: memoryData.dream_context || '',
        } : currentState.honcho,
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
    } catch (e) {
      console.error('DataBridge runSlow error:', e);
      this.slowBackoffMs = Math.min(this.slowBackoffMs * 2, MAX_SLOW_BACKOFF);
    } finally {
      this.scheduleSlow();
    }
  }
}

export const dataBridge = new DataBridge();
