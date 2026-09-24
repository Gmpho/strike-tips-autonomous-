import { HUDState } from '../types';

type Listener = (state: HUDState) => void;

const STORAGE_VERSION = 4;
const STORAGE_VERSION_KEY = 'strike_hud_version';

class HUDStore {
  private state: HUDState = {
    events: {},
    bankroll: {
      balance: 0,
      dailyLimit: 0,
      dailyLoss: 0,
      maxStake: 0,
      totalExposure: 0
    },
    betHistory: [],
    betHistoryTotal: 0,
    betHistoryFull: false,
    betStats: {
      totalBets: 0,
      wins: 0,
      losses: 0,
      stakeTotal: 0,
      payoutTotal: 0,
      roi: 0
    },
    logs: [],
    alerts: [],
    learning: {
      totalRoi: 0,
      samples: 0,
      topTrack: 'N/A',
      accuracy: 0
    },
    bankrollHistory: [],
    honcho: null,
    systemHealth: {
      cpu: 0,
      memory: 0,
      latency: 0,
      status: 'OFFLINE'
    },
    healing: {
      events: [],
      selectors: {},
      githubRuns: []
    },
    vitals: {
      docker: []
    },
    marketMovers: [],
    predictions: [],
    results: [],
    news: [],
    telemetry: [],
    lastUpdate: Date.now()
  };

  private listeners: Set<Listener> = new Set();
  private version = 0;
  private cachedSnapshot: HUDState | null = null;

  constructor() {
    const savedVersion = localStorage.getItem(STORAGE_VERSION_KEY);
    if (savedVersion !== String(STORAGE_VERSION)) {
      localStorage.removeItem('strike_hud_state');
    }
    localStorage.setItem(STORAGE_VERSION_KEY, String(STORAGE_VERSION));

    const saved = localStorage.getItem('strike_hud_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Bankroll is server-owned ephemeral state — NEVER rehydrate it.
        // A stale cache (e.g. pre-paperMode shape, or an old default
        // R1,000/paperMode:false response) renders a wrong "LIVE R1,000"
        // pill until the first poll lands. Always start neutral and let
        // the DataBridge fill it in (Sep-2026 capital flap fix).
        delete parsed.bankroll;
        this.state = { ...this.state, ...parsed };
      } catch (e) {
        console.error('Failed to load HUD state:', e);
      }
    }
  }

  getState() {
    if (!this.cachedSnapshot) {
      this.cachedSnapshot = { ...this.state };
    }
    return this.cachedSnapshot;
  }

  updateState(newState: Partial<HUDState>) {
    Object.assign(this.state, newState);
    this.state.lastUpdate = Date.now();
    this.version++;
    this.cachedSnapshot = null;
    try {
      localStorage.setItem('strike_hud_state', JSON.stringify(this.state));
    } catch (e) {
    }
    this.notify();
  }

  subscribe(listener: Listener) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  private notify() {
    this.listeners.forEach(listener => listener(this.state));
  }
}

export const hudStore = new HUDStore();
