export interface Runner {
  name: string;
  odds: number | string;
  form: string;
  edge?: number;
  winProbability?: number;
  impliedProbability?: number;
  jockeyName?: string;
  trainerName?: string;
}

export interface RaceEvent {
  id: string;
  course: string;
  t: string;
  raceNumber: string;
  runners: Runner[];
  complexity?: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK';
  predictionConfidence?: number;
}

export interface BankrollState {
  balance: number;
  dailyLimit: number;
  dailyLoss: number;
  maxStake: number;
  totalExposure: number;
}

export interface LearningState {
  totalRoi: number;
  samples: number;
  topTrack: string;
  accuracy: number;
}

export interface HealingEvent {
  id: string;
  timestamp: string;
  agent: string;
  action: string;
  status: 'SUCCESS' | 'FAILURE' | 'PENDING';
  details: string;
}

export interface SelectorHealth {
  success_rate: string;
  hits: number;
  misses: number;
}

export interface DockerVital {
  id: string;
  name: string;
  cpu: string;
  mem: string;
  mem_usage: string;
}

export interface HUDState {
  events: Record<string, RaceEvent>;
  bankroll: BankrollState | null;
  learning: LearningState | null;
  systemHealth: {
    cpu: number;
    memory: number;
    latency: number;
    status: 'ONLINE' | 'OFFLINE' | 'DEGRADED';
  };
  healing: {
    events: HealingEvent[];
    selectors: Record<string, Record<string, SelectorHealth>>;
    githubRuns: any[];
  };
  vitals: {
    docker: DockerVital[];
  };
  lastUpdate: number;
}
