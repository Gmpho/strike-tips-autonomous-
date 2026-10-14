import type { RaceEvent } from '../../types';

export type PaceArchetype = 'FRONT_RUNNER' | 'TACTICAL' | 'CLOSER' | 'STRONG_FINISHER';

export interface SimulatedRunner {
  id: string;
  name: string;
  number: string;
  draw: number;
  odds: number;
  winProbability: number;
  margin: number; // lengths behind winner (winner = 0)
  finishOrder: number;
  isAiValue: boolean;
  isFavourite: boolean;
  /** Running style mined from form comments/verdict. Outcome still comes from
   *  winProbability — archetype only directs the mid-race story (who leads early,
   *  who swoops late). */
  paceStyle: PaceArchetype;
  silkColor: string;
  capColor: string;
  earlySpeed: number;
  stamina: number;
  kick: number;
}

export interface SimulationFrame {
  timeSec: number;
  progress: number; // 0 to 1
  runners: {
    id: string;
    x: number; // 0 to 1000 virtual track coordinate
    y: number; // vertical lane coordinate
    currentRank: number;
    hasCrossedFinish: boolean;
    stridePhase: number; // 0 to 1 for galloping animation
  }[];
  leaderboard: {
    order: number;
    number: string;
    name: string;
    margin: number;
    hasFinished: boolean;
    isAiValue: boolean;
    paceStyle: PaceArchetype;
  }[];
}

const SILK_PALETTE = [
  { silk: '#DC2626', cap: '#FFFFFF' }, // 1: Red / White
  { silk: '#FFFFFF', cap: '#18181B' }, // 2: White / Black
  { silk: '#2563EB', cap: '#FFFFFF' }, // 3: Blue / White
  { silk: '#EAB308', cap: '#2563EB' }, // 4: Yellow / Blue (e.g. Sicily style)
  { silk: '#16A34A', cap: '#EAB308' }, // 5: Green / Yellow
  { silk: '#18181B', cap: '#DC2626' }, // 6: Black / Red
  { silk: '#EC4899', cap: '#1E1B4B' }, // 7: Pink / Navy
  { silk: '#8B5CF6', cap: '#F59E0B' }, // 8: Purple / Amber (Secret Tactic style)
  { silk: '#F97316', cap: '#FFFFFF' }, // 9: Orange / White
  { silk: '#06B6D4', cap: '#18181B' }, // 10: Cyan / Black
  { silk: '#991B1B', cap: '#FDE047' }, // 11: Crimson / Yellow
  { silk: '#059669', cap: '#FFFFFF' }, // 12: Emerald / White
  { silk: '#78350F', cap: '#F97316' }, // 13: Brown / Orange
  { silk: '#64748B', cap: '#DC2626' }, // 14: Slate / Red
  { silk: '#D97706', cap: '#1E3A8A' }, // 15: Amber / Blue
  { silk: '#4338CA', cap: '#F43F5E' }, // 16: Indigo / Rose
];

/**
 * Pace-style classifier. Mines the Betfair form text already carried on each
 * runner (`runner_comments` + `verdict`) for running-style phrases the form men
 * use every day. No RAG, no network, deterministic and offline-safe.
 * Priority: FRONT_RUNNER > STRONG_FINISHER > CLOSER > TACTICAL (default).
 * A horse with no form text falls back to TACTICAL — the honest stalker default.
 */
export function classifyPaceStyle(comments?: string, verdict?: string): PaceArchetype {
  const text = `${comments ?? ''} ${verdict ?? ''}`.toLowerCase();
  if (!text.trim()) return 'TACTICAL';
  if (/made all|led\b|led from|disputed (the )?lead|took the lead|front.?run|set the pace|dictat|pressed the leader|prominent|chased the leader|up with the pace/.test(text)) {
    return 'FRONT_RUNNER';
  }
  if (/stayed on( strongly| well)?|ran on( well| strongly)?|finished (well|strongly)|nearest (at the )?finish|flying finish|late run|stayed on gamely|kept on well/.test(text)) {
    return 'STRONG_FINISHER';
  }
  if (/held up|held-up|behind|towards rear|at the rear|in rear|last|slowly away|dwelt|dropped out|mid.?division/.test(text)) {
    return 'CLOSER';
  }
  return 'TACTICAL';
}

/** Archetype → attribute weights. Front-runners break sharp and fade late;
 *  closers are held up then swoop; strong finishers stay on through the line. */
const PACE_ATTRIBUTES: Record<PaceArchetype, { earlySpeed: number; stamina: number; kick: number }> = {
  FRONT_RUNNER: { earlySpeed: 1.12, stamina: 0.9, kick: 0.88 },
  TACTICAL: { earlySpeed: 1.0, stamina: 1.0, kick: 1.0 },
  CLOSER: { earlySpeed: 0.88, stamina: 1.02, kick: 1.08 },
  STRONG_FINISHER: { earlySpeed: 0.92, stamina: 1.08, kick: 1.15 },
};

/** Archetype → pacing-curve exponent. Same finish (margin decides that), but
 *  FRONT_RUNNERs show daylight early and get swallowed late, CLOSERs creep
 *  then pounce — the story the form text promised. */
const PACE_EXPONENT: Record<PaceArchetype, number> = {
  FRONT_RUNNER: 0.85,
  TACTICAL: 1.25,
  CLOSER: 1.6,
  STRONG_FINISHER: 1.45,
};

export const PACE_LABEL: Record<PaceArchetype, string> = {
  FRONT_RUNNER: 'Front-runner',
  TACTICAL: 'Tactical',
  CLOSER: 'Closer',
  STRONG_FINISHER: 'Strong finisher',
};

export function buildSimulatedRunners(
  event: RaceEvent,
  mode: 'EXPECTED' | 'MONTE_CARLO'
): SimulatedRunner[] {
  const runners = event.runners || [];
  if (runners.length === 0) return [];

  // Parse odds & probabilities
  const parsed = runners.map((r, idx) => {
    const oddsNum = typeof r.odds === 'number' ? r.odds : parseFloat(String(r.odds)) || 10.0;
    const implied = oddsNum > 1.0 ? 1.0 / oddsNum : 0.1;
    const prob = typeof r.winProbability === 'number' && r.winProbability > 0 
      ? r.winProbability 
      : implied;
    const drawNum = typeof r.draw === 'number' ? r.draw : idx + 1;
    const clothNum = r.number ? String(r.number) : String(idx + 1);

    const isVal = event.aiSelections?.value?.name === r.name || (typeof r.edge === 'number' && r.edge > 5.0);
    const isFav = event.aiSelections?.favourite?.name === r.name || oddsNum <= 3.0;

    const paletteIdx = idx % SILK_PALETTE.length;

    return {
      id: `${r.name}_${idx}`,
      name: r.name,
      number: clothNum,
      draw: drawNum,
      odds: oddsNum,
      winProbability: prob,
      margin: 0,
      finishOrder: idx + 1,
      isAiValue: !!isVal,
      isFavourite: !!isFav,
      silkColor: SILK_PALETTE[paletteIdx].silk,
      capColor: SILK_PALETTE[paletteIdx].cap,
      earlySpeed: 0.95 + (Math.sin(idx * 1.7) * 0.1),
      stamina: 0.95 + (Math.cos(idx * 2.3) * 0.1),
      kick: 0.95 + (Math.sin(idx * 3.1) * 0.1),
    };
  });

  let orderedRunners: SimulatedRunner[] = [];

  if (mode === 'EXPECTED') {
    // Deterministic: sorted strictly by assessed probability (favourite first)
    orderedRunners = [...parsed].sort((a, b) => b.winProbability - a.winProbability);
    let accumMargin = 0;
    orderedRunners.forEach((r, rank) => {
      if (rank === 0) {
        r.margin = 0.0;
      } else {
        const probGap = Math.max(0.01, orderedRunners[rank - 1].winProbability - r.winProbability);
        const marginStep = Math.min(2.5, Math.max(0.3, probGap * 14.0 + 0.2));
        accumMargin += Math.round(marginStep * 10) / 10;
        r.margin = Math.round(accumMargin * 10) / 10;
      }
      r.finishOrder = rank + 1;
    });
  } else {
    // MONTE CARLO: Stochastic selection based on true win probability
    const pool = [...parsed];
    const picked: SimulatedRunner[] = [];

    while (pool.length > 0) {
      const totalWeight = pool.reduce((acc, curr) => acc + Math.max(0.02, curr.winProbability), 0);
      let rand = Math.random() * totalWeight;
      let selectedIdx = 0;

      for (let i = 0; i < pool.length; i++) {
        rand -= Math.max(0.02, pool[i].winProbability);
        if (rand <= 0) {
          selectedIdx = i;
          break;
        }
      }

      picked.push(pool.splice(selectedIdx, 1)[0]);
    }

    let accumMargin = 0;
    picked.forEach((r, rank) => {
      if (rank === 0) {
        r.margin = 0.0;
      } else {
        const base = 0.3 + Math.random() * 0.8;
        accumMargin += Math.round(base * 10) / 10;
        r.margin = Math.round(accumMargin * 10) / 10;
      }
      r.finishOrder = rank + 1;
    });
    orderedRunners = picked;
  }

  return orderedRunners;
}

export const FINISH_LINE_X = 840; // virtual finish coordinate
export const START_LINE_X = 80;
export const TRACK_LENGTH = FINISH_LINE_X - START_LINE_X;

export function computeSimulationFrame(
  simRunners: SimulatedRunner[],
  elapsedSec: number,
  totalDurationSec: number = 20.0
): SimulationFrame {
  const normTime = Math.min(1.0, Math.max(0.0, elapsedSec / totalDurationSec));
  const finishTime = totalDurationSec - 2.5; // winner crosses at finishTime

  const runnerPositions = simRunners.map((runner, idx) => {
    // Arrival time for this horse at finish line (1 length = 0.17 seconds)
    const arrivalTime = finishTime + (runner.margin * 0.17);
    const hasCrossed = elapsedSec >= arrivalTime;

    let x = START_LINE_X;
    if (elapsedSec < arrivalTime) {
      // Pacing curve:
      // Early break (0 to 0.25), Mid-pack (0.25 to 0.70), Straight (0.70 to 1.0)
      const tProgress = elapsedSec / arrivalTime;

      // Draw bias: low draws get slight rail positioning early
      const drawBonus = (runner.draw <= 4 ? 12 : -8) * Math.sin(tProgress * Math.PI);
      
      // Dynamic easing: cubic out towards finish with organic stride noise
      const baseProg = Math.pow(tProgress, 1.25);
      const strideJitter = Math.sin(elapsedSec * 6 + idx) * 3.5;

      x = START_LINE_X + (baseProg * TRACK_LENGTH) + drawBonus + strideJitter;
    } else {
      // Past the finish line: decelerate smoothly past the wire
      const overTime = elapsedSec - arrivalTime;
      const decel = Math.min(150, overTime * 65);
      x = FINISH_LINE_X + decel;
    }

    // Vertical Y coordinate across track lanes
    const laneHeight = 260 / Math.max(4, simRunners.length);
    const baseY = 80 + (idx * laneHeight);
    const yOsc = Math.sin(elapsedSec * 4 + idx * 1.5) * 2.0;

    // Gallop stride cycle (4 Hz loop)
    const stride = (elapsedSec * 4.2 + (idx * 0.25)) % 1.0;

    return {
      id: runner.id,
      x: Math.min(980, Math.max(20, x)),
      y: baseY + yOsc,
      currentRank: 1, // calculated below
      hasCrossedFinish: hasCrossed,
      stridePhase: stride,
    };
  });

  // Calculate live current ranks by X coordinate
  const sortedByX = [...runnerPositions].sort((a, b) => b.x - a.x);
  sortedByX.forEach((rp, rank) => {
    rp.currentRank = rank + 1;
  });

  // Build live leaderboard
  const leaderboard = simRunners.map((r) => {
    const pos = runnerPositions.find((p) => p.id === r.id);
    return {
      order: pos ? pos.currentRank : r.finishOrder,
      number: r.number,
      name: r.name,
      margin: r.margin,
      hasFinished: pos ? pos.hasCrossedFinish : false,
      isAiValue: r.isAiValue,
    };
  }).sort((a, b) => a.order - b.order);

  return {
    timeSec: elapsedSec,
    progress: normTime,
    runners: runnerPositions,
    leaderboard,
  };
}
