import { HUDState } from '../types';

type Listener = (state: HUDState) => void;

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
    lastUpdate: Date.now()
  };

  private listeners: Set<Listener> = new Set();

  constructor() {
    // Load from localStorage if available
    const saved = localStorage.getItem('strike_hud_state');
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Ensure we merge with defaults in case schema changed
        this.state = { ...this.state, ...parsed };
      } catch (e) {
        console.error('Failed to load HUD state:', e);
      }
    }

    this.state = new Proxy(this.state, {
      set: (target, prop, value) => {
        (target as any)[prop] = value;
        this.notify();
        return true;
      }
    });
  }

  getState() {
    return this.state;
  }

  updateState(newState: Partial<HUDState>) {
    Object.assign(this.state, newState);
    this.state.lastUpdate = Date.now();
    
    // Persist to localStorage
    try {
      localStorage.setItem('strike_hud_state', JSON.stringify(this.state));
    } catch (e) {
      // Silently fail if storage full
    }
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
