import { hudStore } from '../store/hud-store';
import { BETTING_ENDPOINTS } from '../lib/api-prefixes';
import { playAlertTone, playSettleTone, playValueBetTone } from './audio';
import { apiFetch } from '../lib/api-fetch';

const FAST_INTERVAL = 10000;
const SLOW_INTERVAL = 60000;
const MAX_FAST_BACKOFF = 60000;
const MAX_SLOW_BACKOFF = 120000;
// NOTE: the SSE stream (/api/monitoring/stream) was retired 2026-09-15: one
// long-lived connection per open tab billed a 24/7 Modal execution. Snapshot,
// movers, predictor, results, news, and telemetry now arrive via hash-first
// polling (syncSnapshot) + the view-gated slow poll. The backend keeps the
// endpoint for rollback.

export class DataBridge {
  private fastTimer: number | null = null;
  private slowTimer: number | null = null;
  private prevEventCount = 0;
  private prevBetCount = 0;
  private playedValueBets = new Set<string>();
  private fastBackoffMs = FAST_INTERVAL;
  private slowBackoffMs = SLOW_INTERVAL;
  private lastSnapshotHash: string | null = null;
  private refCount = 0;

  start() {
    this.refCount++;
    if (this.refCount > 1) return;
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
  }

  /** Hash-first snapshot sync: tiny hash poll each tick, full download only
   * on change. Replaces the SSE stream (which billed a 24/7 execution per
   * open tab on Modal) with ~10s polling at ~9k invocations/day. */
  private async syncSnapshot() {
    try {
      const hashRes = await apiFetch('/api/monitoring/snapshot-hash');
      if (!hashRes.ok) return;
      const { snapshot_hash } = await hashRes.json();
      if (!snapshot_hash || snapshot_hash === this.lastSnapshotHash) return;
      const fullRes = await apiFetch('/api/monitoring/snapshot');
      if (!fullRes.ok) return;
      const data = await fullRes.json();
      this.lastSnapshotHash = data.snapshot_hash || snapshot_hash;
      const current = hudStore.getState();
      const patch: Record<string, unknown> = {
        events: data.events || {},
        alerts: data.alerts || [],
      };
      const unwrap = (v: unknown): unknown => {
        // Bundle files wrap arrays ({movers: [...], timestamp}); SSE used to
        // send bare arrays. Accept both shapes.
        if (Array.isArray(v)) return v;
        if (v && typeof v === 'object') {
          const o = v as Record<string, unknown>;
          for (const k of ['movers', 'predictions', 'results', 'items', 'events']) {
            if (Array.isArray(o[k])) return o[k];
          }
        }
        return v;
      };
      if (data.movers !== undefined && data.movers !== null) patch.marketMovers = unwrap(data.movers);
      if (data.predictor !== undefined && data.predictor !== null) patch.predictions = unwrap(data.predictor);
      if (data.results !== undefined && data.results !== null) patch.results = unwrap(data.results);
      const newsItems = Array.isArray(data.news) ? data.news : data.news?.items;
      if (Array.isArray(newsItems) && newsItems.length > 0) patch.news = newsItems;
      if (Array.isArray(data.telemetry)) this.mergeTelemetry(data.telemetry);
      hudStore.updateState(patch);
      this.playSoundsForChanges(data, null, { bets: current.betHistory });
    } catch (err) {
      console.error('Snapshot sync failed:', err);
    }
  }

  private mergeTelemetry(fresh: Array<{ engine: string; badge: string; message: string; ts: number }>) {
    if (!Array.isArray(fresh) || fresh.length === 0) return;
    const existing = hudStore.getState().telemetry || [];
    const seen = new Set(existing.map(t => `${t.engine}|${t.message}|${t.ts}`));
    const merged = [...fresh.filter(t => !seen.has(`${t.engine}|${t.message}|${t.ts}`)), ...existing].slice(0, 30);
    hudStore.updateState({ telemetry: merged });
  }

  /** One-shot REST hydration for news + telemetry on startup. */
  private async hydrateFeeds() {
    // Run news + telemetry hydration in parallel — the sequential await here
    // delayed telemetry by however long the (slow) news fetch took.
    await Promise.all([this.hydrateNews(), this.hydrateTelemetry()]);
  }

  private async hydrateTelemetry() {
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
        this.syncSnapshot(),
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
          // Preserve ledger identity on every poll — dropping these flips the
          // UI to LIVE and hides the paper/real split (Sep-2026 bug).
          paperMode: bankroll.paperMode,
          paperBalance: bankroll.paperBalance,
          realBalance: bankroll.realBalance,
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
      // NOTE: 'exotics' must stay here — its Settle Ledger reads betHistory.
      const needHistory = ['bankroll', 'analytics', 'exotics'].includes(activeView || '');
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
