import { HUDState } from '../types';

type Listener = (state: HUDState) => void;

const STORAGE_VERSION = 3;
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
