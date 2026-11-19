export interface Runner {
  name: string;
  odds: number | string;
  form: string;
  edge?: number;
  winProbability?: number;
  impliedProbability?: number;
  jockeyName?: string;
  trainerName?: string;
  age?: string | number;
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
  /** Enriched Betfair form fields (all regions, optional) */
  runner_comments?: string;
  jockey_claim?: string;
  official_rating?: number;
  pedigree?: string;
  owner?: string;
  verdict?: string;
  // Aliases for Betfair-enriched trainer/age/weight/form when not from TAB
  trainer?: string;
  ageNum?: number;
}

export interface RaceEvent {
  id: string;
  course: string;
  t: string;
  raceNumber: string;
  runners: Runner[];
  /** Race distance in metres (Betfair-derived, when available). */
  distance_m?: number;
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
  /** Active betting bank: paperBalance when paperMode, else realBalance.
   *  null until the governor has seeded state (no fake defaults). */
  balance: number | null;
  dailyLimit: number;
  dailyLoss: number;
  maxStake: number;
  totalExposure: number;
  paperMode?: boolean;
  /** Paper simulation ledger; null until seeded (JSON null, not fake default). */
  paperBalance?: number | null;
  /** Real-funds ledger (untouched while paperMode is on); null until seeded. */
  realBalance?: number | null;
}

export interface LearningState {
  totalRoi: number;
  samples: number;
  topTrack: string;
  accuracy: number;
  roiByTrack?: Record<string, number>;
  roiByOddsRange?: Record<string, any>;
  /** Ledger-derived per-track detail (sample + recency gated). */
  trackStats?: Record<string, TrackStat>;
  bestTrack?: RankedTrack | null;
  worstTrack?: RankedTrack | null;
  minSample?: number;
  recencyDays?: number;
  /** ROI whose per-ticket return is capped — what the track cards rank on. */
  roiCappedByTrack?: Record<string, number>;
  cap?: number;
  /** Per-book track payloads; `books.real` and `books.paper` never mix. */
  books?: { real: BookTracks; paper: BookTracks };
  /** Calibration per book, plus the blended flat keys above. */
  calibration?: {
    accuracy: number;
    samples: number;
    actualWinRate: number;
    impliedWinRate: number;
    books?: Record<string, { accuracy: number; samples: number; actualWinRate: number; impliedWinRate: number }>;
  };
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
  status?: string;
  notes?: string;
  /** Paper simulation ticket (absent/false = real money). */
  is_paper?: boolean;
}

export interface BetStats {
  totalBets: number;
  wins: number;
  losses: number;
  stakeTotal: number;
  payoutTotal: number;
  roi: number;
  /** Ledger buckets (Oct-2026: VOID/EXPIRED are refunds, not pending). */
  settledBets?: number;
  pendingBets?: number;
  voidBets?: number;
  expiredBets?: number;
  settlementRate?: number;
  allStakeTotal?: number;
  avgStake?: number;
  /** Gross returns / lost stakes; null when nothing has lost yet. */
  profitFactor?: number | null;
  /** Disclosure only: expired tickets counted as losses. */
  roiIncludingExpired?: number;
  /** Win rate per book — the flat keys above are the blended ledger. */
  winRate?: number;
  unresolved?: number;
  unresolvedShare?: number;
  lastSettled?: string | null;
  /** Real-money and paper ledgers, never to be averaged. */
  books?: { real: BookStats; paper: BookStats };
}

export interface TrackStat {
  roi: number;
  n: number;
  wins: number;
  staked: number;
  returned: number;
  lastSeen: string | null;
  daysSince: number | null;
  eligible: boolean;
  /** ROI with each ticket's return capped at `cap` x stake — the ranking number. */
  roiCapped?: number;
  cap?: number;
  /** The single ticket that drives this track's return. */
  topTicket?: { horse: string; stake: number; returned: number; odds: number } | null;
  /** % of the track's total return that one ticket accounts for. */
  topShare?: number | null;
}

/** One book (real money / paper simulation) of ledger-derived statistics. */
export interface BookStats {
  totalBets: number;
  settledBets: number;
  wins: number;
  losses: number;
  /** Wins/losses that carry a stake and (for a win) a return. */
  provenWins?: number;
  provenLosses?: number;
  /** Settled as WON/LOST but with no stake or no return — unproven. */
  unprovenWins?: number;
  unprovenLosses?: number;
  /** Win rate over proven tickets only; null when there are none. */
  provenWinRate?: number | null;
  expiredBets: number;
  pendingBets: number;
  /** Wins / settled tickets, per book. Never blend the two books. */
  winRate?: number;
  stakeTotal: number;
  payoutTotal: number;
  roi: number;
  /** Disclosure only: expired tickets counted as losses (refunds are not losses). */
  roiIncludingExpired?: number;
  profitFactor?: number | null;
  /** Tickets that never produced a result at all. */
  unresolved?: number;
  unresolvedShare?: number;
  lastSettled?: string | null;
  avgStake?: number;
  settlementRate?: number;
}

/** Per-track payload for one book. */
export interface BookTracks {
  roiByTrack: Record<string, number>;
  roiCappedByTrack?: Record<string, number>;
  trackStats: Record<string, TrackStat>;
  bestTrack?: RankedTrack | null;
  worstTrack?: RankedTrack | null;
  minSample?: number;
  recencyDays?: number;
  cap?: number;
}

export interface RankedTrack extends TrackStat {
  name: string;
}

export interface MarketMover {
  horse: string;
  course: string;
  time: string;
  current_odds: string;
  first_show: string;
  movement: string;
  /** ATR meeting region (Oct-2026 scraper repair). Absent on old snapshots. */
  region?: string;
  /** Canonical-event fields (Live Intelligence). Additive: old feeds omit them. */
  id?: string;
  /** `snapshot` = our own 5-min diff (primary); `atr` = fallback page. */
  source?: 'snapshot' | 'atr' | string;
  /** How old this row's data is, in seconds. Never absent on new feeds. */
  age_secs?: number | null;
  move_pct?: number | string | null;
  direction?: 'shortened' | 'drifted' | 'stable' | string;
  severity?: 'steamer' | 'drifter' | 'move' | string;
  /** True when the runner is the user's own league pick. */
  is_user_pick?: boolean;
  race_number?: number | string | null;
  timestamp?: string;
}

export interface Predictor {
  horse: string;
  raw: string;
  prediction: string;
  /** ATR meeting context (Oct-2026 scraper repair). Absent on old snapshots. */
  course?: string;
  region?: string;
  time?: string;
  /** ISO day of the racecard the prediction belongs to (Nov-2026: the feed
   *  used to mix yesterday's "Recent Winners" digest into today's list). */
  date?: string;
  /** "exacta" means `horse` is a readable "A / B" pair — ATR files both legs
   *  in one cell and they must not be split into two invented picks. */
  type?: 'single' | 'exacta';
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
  /** Full ledger size; betHistory may hold a paint-fast window (?limit). */
  betHistoryTotal: number;
  /** User expanded past the window — polls must keep fetching full. */
  betHistoryFull: boolean;
  /** A history fetch has resolved at least once (vs still loading). */
  betHistoryReady: boolean;
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
  /** Epoch ms of the last successful market-snapshot download. The odds
   *  monitor writes the card every 5 min; the HUD shows races as "synced"
   *  relative to this so a stalled feed is visible, not assumed live. */
  lastSyncTs: number;
  /** Feed health as stamped by the odds monitor (Nov-2026). `fetch_ok` is
   *  false whenever the Betway cycle failed and the snapshot is a reuse of an
   *  older card; `stale` marks the empty-snapshot guard's recovered copy.
   *  Both must be surfaced — a card of hours-old prices must never look live. */
  feedOk: boolean | null;
  feedStale: boolean;
  feedError: string | null;
  /** Epoch ms this tab first saw a not-live feed (cleared on recovery). */
  feedStaleSince: number | null;
  lastUpdate: number;
}
