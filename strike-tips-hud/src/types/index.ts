export interface Runner {
  name: string;
  odds: number | string;
  form: string;
  edge?: number;
  winProbability?: number;
  impliedProbability?: number;
  jockeyName?: string;
  trainerName?: string;
  age?: string;
  weight?: string;
  draw?: number;
  number?: string;
  starRating?: number;
  timeForm?: string;
  outcomeName?: string;
  region?: string;
  swarmInsight?: string;
  insightSource?: string;
  insightTs?: string;
  /** Betfair SA normalized gear tokens, e.g. "Hood · Blinkers". Absent when unknown. */
  gear?: string;
  /** Days since the horse's last run (Betfair SA). Absent when unknown. */
  daysSinceRun?: number;
}

export interface RaceEvent {
  id: string;
  course: string;
  t: string;
  raceNumber: string;
  runners: Runner[];
  complexity?: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK';
  predictionConfidence?: number;
  dsi?: number;
  aiSelections?: {
    value?: Runner;
    favourite?: Runner;
    outsider?: Runner;
  };
}

export interface BankrollState {
  balance: number;
  dailyLimit: number;
  dailyLoss: number;
  maxStake: number;
  totalExposure: number;
  paperMode?: boolean;
  paperBalance?: number;
}

export interface LearningState {
  totalRoi: number;
  samples: number;
  topTrack: string;
  accuracy: number;
  roiByTrack?: Record<string, number>;
  roiByOddsRange?: Record<string, any>;
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

export interface BetRecord {
  id: string;
  track: string;
  raceNumber: number;
  horse: string;
  odds: number;
  edgePercent: number;
  stake: number;
  confidence: string;
  placedAt: string;
  settled: boolean;
  won?: boolean;
  payout?: number;
  notes?: string;
}

export interface BetStats {
  totalBets: number;
  wins: number;
  losses: number;
  stakeTotal: number;
  payoutTotal: number;
  roi: number;
}

export interface MarketMover {
  horse: string;
  course: string;
  time: string;
  current_odds: string;
  first_show: string;
  movement: string;
}

export interface Predictor {
  horse: string;
  raw: string;
  prediction: string;
}

export interface NewsItem {
  id: string;
  title: string;
  url: string;
  source: string;
  region: string;
  summary: string;
  image_url: string;
  published: string;
}

export interface TelemetryEvent {
  ts: number;
  engine: 'swarm' | 'news' | 'dream' | 'governor' | 'system' | string;
  badge: string;
  message: string;
}

export interface ResultRunner {
  name: string;
  position: string;
  odds: string;
  odds_decimal: number | null;
  form: string;
}

export interface ResultRace {
  course: string;
  date: string;
  time: string;
  title: string;
  runners: ResultRunner[];
}

export interface HUDState {
  events: Record<string, RaceEvent>;
  bankroll: BankrollState | null;
  betHistory: BetRecord[];
  betStats: BetStats | null;
  logs: string[];
  alerts: any[];
  learning: LearningState | null;
  bankrollHistory: Array<{ t: string; balance: number }>;
  honcho: { status: string; context: string; dreamContext: string } | null;
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
  marketMovers: MarketMover[];
  predictions: Predictor[];
  results: ResultRace[];
  news: NewsItem[];
  telemetry: TelemetryEvent[];
  lastUpdate: number;
}
