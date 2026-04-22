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
  lastUpdate: number;
}
