import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useHUD } from '../../hooks/useHUD';
import type { RaceEvent, Runner } from '../../types';
import { 
  Play, Pause, RotateCcw, Zap, Dices, Award, 
  Sparkles, Activity, Calendar, Timer
} from 'lucide-react';
import { 
  buildSimulatedRunners, 
  computeSimulationFrame, 
  type SimulatedRunner, 
  type SimulationFrame 
} from '../../engine/simulation/pacingEngine';
import { RaceTrackCanvas } from '../simulator/RaceTrackCanvas';

/* ── Demo race data (offline fallback) ─────────────────────────────── */
const mkRunner = (
  name: string, odds: number, draw: number, num: string, form: string,
  extra?: Partial<Runner>
): Runner => ({
  name, odds, draw, number: num, form,
  winProbability: 1 / odds,
  impliedProbability: 1 / odds,
  edge: Math.max(0, Math.random() * 12 - 2),
  ...extra,
});

const DEMO_RACES: RaceEvent[] = [
  {
    id: 'demo-kenilworth-r4',
    course: 'Kenilworth',
    t: '14:30',
    raceNumber: '4',
    distance_m: 1400,
    complexity: 'MEDIUM_RISK',
    runners: [
      mkRunner('Silver Thorn', 3.5, 1, '1', '1-2-3-1', { jockeyName: 'R Fourie' }),
      mkRunner('Cape Flyer', 4.0, 2, '2', '2-1-4-2', { jockeyName: 'A Marcus' }),
      mkRunner('Secret Tactic', 7.0, 3, '3', '3-5-1-6', { jockeyName: 'R Munger' }),
      mkRunner('Gold Standard', 8.5, 4, '4', '4-3-5-4', { jockeyName: 'L Hewitson' }),
      mkRunner('Storm Signal', 12.0, 5, '5', '5-7-3-8', { jockeyName: 'K De Melo' }),
      mkRunner('Lucky Strike', 15.0, 6, '6', '6-4-9-5', { jockeyName: 'M Yeni' }),
      mkRunner('Mountain Echo', 20.0, 7, '7', '8-6-7-9'),
      mkRunner('Dawn Patrol', 25.0, 8, '8', '7-9-8-10'),
    ],
    aiSelections: {
      value: mkRunner('Secret Tactic', 7.0, 3, '3', '3-5-1-6'),
      favourite: mkRunner('Silver Thorn', 3.5, 1, '1', '1-2-3-1'),
      outsider: mkRunner('Dawn Patrol', 25.0, 8, '8', '7-9-8-10'),
    },
  },
  {
    id: 'demo-durbanville-r6',
    course: 'Durbanville',
    t: '15:15',
    raceNumber: '6',
    distance_m: 1600,
    complexity: 'HIGH_RISK',
    runners: [
      mkRunner('Fire Dragon', 2.8, 1, '1', '1-1-2-1', { jockeyName: 'A Marcus' }),
      mkRunner('Royal Decree', 5.5, 2, '2', '3-2-1-3', { jockeyName: 'R Fourie' }),
      mkRunner('Storm Chaser', 6.0, 3, '3', '2-4-3-2', { jockeyName: 'G Cheyne' }),
      mkRunner('Golden Arrow', 9.0, 4, '4', '5-3-6-4', { jockeyName: 'L Hewitson' }),
      mkRunner('Iron Will', 11.0, 5, '5', '4-6-5-7', { jockeyName: 'R Munger' }),
      mkRunner('Silent Runner', 18.0, 6, '6', '7-8-4-9'),
      mkRunner('Ocean Breeze', 22.0, 7, '7', '6-9-8-8'),
      mkRunner('Midnight Sun', 30.0, 8, '8', '9-7-10-6'),
      mkRunner('Desert Prince', 35.0, 9, '9', '8-10-9-11'),
      mkRunner('Wild Card', 50.0, 10, '10', '10-11-7-12'),
    ],
    aiSelections: {
      value: mkRunner('Storm Chaser', 6.0, 3, '3', '2-4-3-2'),
      favourite: mkRunner('Fire Dragon', 2.8, 1, '1', '1-1-2-1'),
      outsider: mkRunner('Wild Card', 50.0, 10, '10', '10-11-7-12'),
    },
  },
  {
    id: 'demo-turffontein-r3',
    course: 'Turffontein',
    t: '13:45',
    raceNumber: '3',
    distance_m: 1200,
    complexity: 'LOW_RISK',
    runners: [
      mkRunner('Highveld Hero', 2.2, 1, '1', '1-1-1-2', { jockeyName: 'C Maujean' }),
      mkRunner('Joburg Express', 6.0, 2, '2', '2-3-2-1', { jockeyName: 'M Yeni' }),
      mkRunner('Reef Runner', 8.0, 3, '3', '3-2-4-3', { jockeyName: 'S Khumalo' }),
      mkRunner('Braamfontein', 10.0, 4, '4', '4-5-3-5'),
      mkRunner('Sandton Sunset', 14.0, 5, '5', '5-4-6-4'),
      mkRunner('Soweto Star', 20.0, 6, '6', '6-7-5-8'),
    ],
    aiSelections: {
      value: mkRunner('Joburg Express', 6.0, 2, '2', '2-3-2-1'),
      favourite: mkRunner('Highveld Hero', 2.2, 1, '1', '1-1-1-2'),
      outsider: mkRunner('Soweto Star', 20.0, 6, '6', '6-7-5-8'),
    },
  },
];
/* ─────────────────────────────────────────────────────────────────── */

interface RaceSimulatorViewProps {
  initialRaceEvent?: RaceEvent;
  onNavigate?: (view: string) => void;
}

export const RaceSimulatorView: React.FC<RaceSimulatorViewProps> = ({
  initialRaceEvent,
}) => {
  const store = useHUD();
  const [isDemo, setIsDemo] = useState(false);

  const events = useMemo(() => {
    const raw = store.events;
    let list: RaceEvent[] = [];
    if (Array.isArray(raw)) {
      list = raw as RaceEvent[];
    } else if (raw && typeof raw === 'object') {
      list = Object.values(raw) as RaceEvent[];
    }
    if (initialRaceEvent && !list.some((e) => e.id === initialRaceEvent.id)) {
      list = [initialRaceEvent, ...list];
    }
    // Fallback to demo races when no live data is available
    if (list.length === 0) {
      setIsDemo(true);
      return DEMO_RACES;
    }
    setIsDemo(false);
    return list;
  }, [store.events, initialRaceEvent]);

  // Select active race (from prop, or default to first event with runners)
  const [selectedEventId, setSelectedEventId] = useState<string>(() => {
    if (initialRaceEvent?.id) return initialRaceEvent.id;
    return '';
  });

  // Keep selected event synced if initialRaceEvent or events change
  useEffect(() => {
    if (initialRaceEvent?.id) {
      setSelectedEventId(initialRaceEvent.id);
    } else if ((!selectedEventId || !events.some((e) => e.id === selectedEventId)) && events.length > 0) {
      setSelectedEventId(events[0].id);
    }
  }, [initialRaceEvent, events, selectedEventId]);

  const activeEvent = useMemo(() => {
    if (selectedEventId) {
      const found = events.find((e) => e.id === selectedEventId);
      if (found) return found;
    }
    return initialRaceEvent || events[0] || null;
  }, [events, selectedEventId, initialRaceEvent]);

  // Simulator State
  const [mode, setMode] = useState<'EXPECTED' | 'MONTE_CARLO'>('EXPECTED');
  const [isPlaying, setIsPlaying] = useState<boolean>(true);
  const [speed, setSpeed] = useState<number>(1.0);
  const [highlightValueBet, setHighlightValueBet] = useState<boolean>(true);
  const [selectedHorse, setSelectedHorse] = useState<SimulatedRunner | null>(null);

  const [elapsedSec, setElapsedSec] = useState<number>(0);
  const totalDuration = 20.0;

  // Build runners whenever active event or mode changes
  const [simRunners, setSimRunners] = useState<SimulatedRunner[]>([]);

  const regenerateRunners = (targetMode: 'EXPECTED' | 'MONTE_CARLO') => {
    if (!activeEvent) return;
    const list = buildSimulatedRunners(activeEvent, targetMode);
    setSimRunners(list);
    setElapsedSec(0);
    setIsPlaying(true);
    setSelectedHorse(null);
  };

  useEffect(() => {
    if (activeEvent) {
      regenerateRunners(mode);
    }
  }, [activeEvent?.id, mode]);

  // Animation frame loop
  const lastTimeRef = useRef<number | null>(null);
  const reqRef = useRef<number | null>(null);

  useEffect(() => {
    if (!isPlaying) {
      lastTimeRef.current = null;
      if (reqRef.current) cancelAnimationFrame(reqRef.current);
      return;
    }

    const loop = (timestamp: number) => {
      if (lastTimeRef.current !== null) {
        const delta = (timestamp - lastTimeRef.current) / 1000;
        setElapsedSec((prev) => {
          const next = prev + delta * speed;
          if (next >= totalDuration) {
            setIsPlaying(false);
            return totalDuration;
          }
          return next;
        });
      }
      lastTimeRef.current = timestamp;
      reqRef.current = requestAnimationFrame(loop);
    };

    reqRef.current = requestAnimationFrame(loop);

    return () => {
      if (reqRef.current) cancelAnimationFrame(reqRef.current);
    };
  }, [isPlaying, speed, totalDuration]);

  // Compute current frame
  const currentFrame: SimulationFrame | null = useMemo(() => {
    if (simRunners.length === 0) return null;
    return computeSimulationFrame(simRunners, elapsedSec, totalDuration);
  }, [simRunners, elapsedSec, totalDuration]);

  if (!activeEvent || events.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center p-8 text-center min-h-[500px]">
        <Activity className="w-12 h-12 text-purple-500/40 animate-pulse mb-4" />
        <h2 className="text-xl font-bold text-white mb-2">Initialising Simulator…</h2>
        <p className="text-sm text-zinc-400 max-w-md">
          Loading demo race data. This should only take a moment.
        </p>
      </div>
    );
  }

  return (
    <div className="flex-1 w-full max-w-7xl mx-auto px-3 sm:px-6 py-4 sm:py-6 space-y-6">
      
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-theme/40 pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-[10px] font-black tracking-widest text-emerald-400 uppercase">
              AI Broadcast Engine · 60 FPS Canvas
            </span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-white uppercase tracking-tight flex items-center gap-2">
            <span>Race Predictor Simulator</span>
            <Zap className="w-6 h-6 text-purple-400 fill-purple-400" />
          </h1>
          <p className="text-xs sm:text-sm text-zinc-400 mt-1">
            Simulate the final 300m finish in real time. Switch between consensus expectations and probabilistic reality.
          </p>
          {isDemo && (
            <div className="mt-2 flex items-center gap-2 px-3 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-xs">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
              <span className="text-amber-300 font-bold">DEMO MODE</span>
              <span className="text-amber-200/70">— Backend offline · showing SA showcase races · live data auto-syncs when connected</span>
            </div>
          )}
        </div>

        {/* Global Stats Badge */}
        <div className="flex items-center gap-3 bg-zinc-900/80 border border-theme px-4 py-2 rounded-xl text-xs font-mono">
          <div>
            <div className="text-[9px] text-zinc-500 font-bold uppercase">Active Races</div>
            <div className="text-white font-bold">{events.length} Today</div>
          </div>
          <div className="w-px h-6 bg-zinc-800" />
          <div>
            <div className="text-[9px] text-zinc-500 font-bold uppercase">Physics Engine</div>
            <div className="text-purple-400 font-bold">Pacing v2.1</div>
          </div>
        </div>
      </div>

      {/* Race Selector Pill Strip */}
      <div className="space-y-1.5">
        <div className="text-[10px] font-black text-zinc-400 uppercase tracking-wider flex items-center gap-1.5">
          <Calendar className="w-3 h-3 text-purple-400" />
          <span>Select Today&apos;s Race Card</span>
        </div>
        <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none">
          {events.map((ev) => {
            const isSelected = ev.id === activeEvent.id;
            return (
              <button
                key={ev.id}
                onClick={() => setSelectedEventId(ev.id)}
                className={`flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition-all border cursor-pointer ${
                  isSelected
                    ? 'bg-purple-600 text-white border-purple-400 shadow-[0_0_15px_rgba(168,85,247,0.4)]'
                    : 'bg-zinc-900/60 text-zinc-400 border-zinc-800 hover:text-white hover:border-zinc-700'
                }`}
              >
                <span className="uppercase">{ev.course}</span>
                <span className={`px-1.5 py-0.2 rounded text-[10px] ${isSelected ? 'bg-purple-800 text-purple-100' : 'bg-zinc-800 text-zinc-300'}`}>
                  R{ev.raceNumber}
                </span>
                {ev.t && (
                  <span className="text-[10px] font-mono opacity-80">{ev.t}</span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Theatre Arena */}
      <div className="bg-zinc-950 border border-theme/60 rounded-2xl sm:rounded-3xl p-3 sm:p-6 shadow-2xl space-y-4">
        
        {/* Arena Top Toolbar */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-3">
          <div className="flex items-center gap-3">
            <div className="px-3 py-1 rounded-lg bg-zinc-900 border border-purple-500/30 text-white font-black text-sm uppercase flex items-center gap-2">
              <span className="text-purple-400">{activeEvent.course}</span>
              <span>RACE {activeEvent.raceNumber}</span>
              {activeEvent.distance_m && (
                <span className="text-xs text-zinc-400 font-mono">({activeEvent.distance_m}m)</span>
              )}
            </div>
            {activeEvent.t && (
              <div className="hidden sm:flex items-center gap-1.5 text-xs text-zinc-400 font-mono">
                <Timer className="w-3.5 h-3.5 text-zinc-500" />
                <span>OFF: {activeEvent.t}</span>
              </div>
            )}
          </div>

          {/* Mode Switcher */}
          <div className="flex items-center gap-2">
            <div className="flex items-center bg-zinc-900 rounded-xl p-1 border border-zinc-800 text-xs">
              <button
                onClick={() => {
                  setMode('EXPECTED');
                  regenerateRunners('EXPECTED');
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-all ${
                  mode === 'EXPECTED'
                    ? 'bg-purple-600 text-white shadow-xs'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Award className="w-3.5 h-3.5" />
                <span>Expected (Consensus)</span>
              </button>
              <button
                onClick={() => {
                  setMode('MONTE_CARLO');
                  regenerateRunners('MONTE_CARLO');
                }}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-bold cursor-pointer transition-all ${
                  mode === 'MONTE_CARLO'
                    ? 'bg-amber-600 text-white shadow-xs'
                    : 'text-zinc-400 hover:text-white'
                }`}
              >
                <Dices className="w-3.5 h-3.5" />
                <span>Monte Carlo (Reality)</span>
              </button>
            </div>

            {/* Value Bet Spotlight Toggle */}
            <button
              onClick={() => setHighlightValueBet(!highlightValueBet)}
              className={`flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-bold border cursor-pointer transition-all ${
                highlightValueBet
                  ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-xs'
                  : 'bg-zinc-900 text-zinc-400 border-zinc-800 hover:text-zinc-200'
              }`}
            >
              <Zap className="w-3.5 h-3.5 text-emerald-400" />
              <span>Spotlight AI Value</span>
            </button>
          </div>
        </div>

        {/* 60 FPS Panoramic Track Canvas */}
        <div className="w-full">
          <RaceTrackCanvas
            simRunners={simRunners}
            frame={currentFrame}
            highlightValueBet={highlightValueBet}
            onHorseClick={(r) => setSelectedHorse(r)}
          />
        </div>

        {/* Playback Controls & Scrubber */}
        <div className="bg-zinc-900/60 rounded-xl p-3 border border-zinc-800/80 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsPlaying(!isPlaying)}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-black bg-purple-600 hover:bg-purple-500 text-white shadow-md transition-all cursor-pointer"
            >
              {isPlaying ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
              <span>{isPlaying ? 'PAUSE' : 'PLAY'}</span>
            </button>

            <button
              onClick={() => {
                setElapsedSec(0);
                setIsPlaying(true);
              }}
              className="flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-bold bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-700 transition-all cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>RESET RACE</span>
            </button>

            {/* Speed Selector */}
            <div className="flex items-center bg-zinc-950 rounded-lg p-0.5 border border-zinc-800 text-xs">
              {[1.0, 1.5, 2.0].map((s) => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2.5 py-1 rounded text-xs font-bold cursor-pointer transition-colors ${
                    speed === s ? 'bg-purple-500 text-white' : 'text-zinc-400 hover:text-zinc-200'
                  }`}
                >
                  {s}x
                </button>
              ))}
            </div>
          </div>

          {/* Scrubber & Timestamp */}
          <div className="flex items-center gap-3 flex-1 max-w-md min-w-[200px]">
            <span className="text-xs font-mono text-zinc-400 font-bold shrink-0">
              {elapsedSec.toFixed(1)}s / {totalDuration.toFixed(1)}s
            </span>
            <div className="flex-1 h-2 bg-zinc-950 rounded-full overflow-hidden border border-zinc-800">
              <div
                className="h-full bg-gradient-to-r from-purple-500 via-indigo-500 to-emerald-400 transition-all duration-75"
                style={{ width: `${(elapsedSec / totalDuration) * 100}%` }}
              />
            </div>
          </div>
        </div>

        {/* Selected Runner Strip */}
        {selectedHorse && (
          <div className="p-3 rounded-xl bg-purple-950/30 border border-purple-500/40 flex flex-wrap items-center justify-between gap-3 animate-in fade-in">
            <div className="flex items-center gap-2.5">
              <span className="px-2 py-0.5 rounded-lg bg-purple-500 text-white font-black text-xs">
                #{selectedHorse.number}
              </span>
              <div>
                <span className="text-sm font-black text-white">{selectedHorse.name}</span>
                <span className="text-xs text-zinc-400 ml-2">Barrier Draw {selectedHorse.draw}</span>
              </div>
              {selectedHorse.isAiValue && (
                <span className="text-[10px] font-black text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/30">
                  AI BEST VALUE
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="text-zinc-400">Odds: <strong className="text-white text-sm">{selectedHorse.odds.toFixed(2)}</strong></span>
              <span className="text-zinc-400">Assessed Win Chance: <strong className="text-emerald-400 text-sm">{(selectedHorse.winProbability * 100).toFixed(1)}%</strong></span>
              <span className="text-zinc-400">Finish Margin: <strong className="text-purple-400 text-sm">+{selectedHorse.margin.toFixed(1)}L</strong></span>
            </div>
          </div>
        )}

        {/* Lower Grid: Order of Finish Leaderboard & Insights */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 pt-2">
          
          {/* Order of Finish Table (2 cols) */}
          <div className="lg:col-span-2 bg-zinc-900/60 rounded-xl p-4 border border-zinc-800 space-y-3">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <div className="flex items-center gap-2">
                <span className="text-xs font-black uppercase tracking-wider text-white">
                  Order of Finish Leaderboard
                </span>
                <span className="text-[10px] px-2 py-0.5 rounded bg-zinc-800 text-zinc-400 font-mono">
                  {simRunners.length} Runners
                </span>
              </div>
              <span className="text-[10px] font-mono text-zinc-500 uppercase">
                Length Behind (1L = 0.17s)
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono">
                <thead>
                  <tr className="text-zinc-500 border-b border-zinc-800/60 text-[10px]">
                    <th className="py-1.5 px-2">POS</th>
                    <th className="py-1.5 px-2">HORSE</th>
                    <th className="py-1.5 px-2">DRAW</th>
                    <th className="py-1.5 px-2">ODDS</th>
                    <th className="py-1.5 px-2">WIN PROB</th>
                    <th className="py-1.5 px-2 text-right">MARGIN</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-zinc-800/40">
                  {currentFrame?.leaderboard.map((row, idx) => {
                    const runnerMeta = simRunners.find((r) => r.number === row.number);
                    const isVal = row.isAiValue;
                    return (
                      <tr
                        key={`${row.number}_${row.name}`}
                        onClick={() => runnerMeta && setSelectedHorse(runnerMeta)}
                        className={`transition-colors cursor-pointer ${
                          isVal && highlightValueBet
                            ? 'bg-purple-500/15 text-purple-200 font-bold'
                            : idx === 0
                              ? 'bg-amber-500/10 text-amber-300 font-bold'
                              : 'text-zinc-300 hover:bg-white/5'
                        }`}
                      >
                        <td className="py-2 px-2 font-black">
                          {idx === 0 ? <span className="text-amber-400">1st</span> : `${idx + 1}`}
                        </td>
                        <td className="py-2 px-2">
                          <div className="flex items-center gap-2">
                            <span className="w-5 h-5 rounded flex items-center justify-center bg-zinc-800 text-white text-[10px] font-bold">
                              {row.number}
                            </span>
                            <span className="font-bold text-white text-xs">{row.name}</span>
                            {isVal && (
                              <span className="text-[8px] bg-purple-500/20 text-purple-300 px-1 py-0.2 rounded border border-purple-500/30">
                                VALUE
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="py-2 px-2 text-zinc-400">
                          D{runnerMeta?.draw ?? '-'}
                        </td>
                        <td className="py-2 px-2 text-white font-bold">
                          {runnerMeta ? runnerMeta.odds.toFixed(2) : '-'}
                        </td>
                        <td className="py-2 px-2 text-emerald-400">
                          {runnerMeta ? `${(runnerMeta.winProbability * 100).toFixed(1)}%` : '-'}
                        </td>
                        <td className="py-2 px-2 text-right font-black">
                          {idx === 0 ? (
                            <span className="text-emerald-400">WINNER</span>
                          ) : (
                            `+${row.margin.toFixed(1)}L`
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Educational Insights Card (1 col) */}
          <div className="bg-zinc-900/60 rounded-xl p-4 border border-zinc-800 space-y-3.5 flex flex-col justify-between">
            <div className="space-y-2.5">
              <div className="flex items-center gap-2 text-purple-400 font-bold text-xs uppercase">
                <Sparkles className="w-4 h-4" />
                <span>Simulation Intelligence</span>
              </div>
              
              <div className="p-3 rounded-lg bg-zinc-950/80 border border-zinc-800 text-xs text-zinc-300 space-y-2">
                <p className="font-bold text-white">Why Monte Carlo Reality Matters:</p>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  Broadcast simulators on TV (like Racing 240) only show <strong>Expected mode</strong>—running the race once where the heavy favourite always crosses the line first.
                </p>
                <p className="text-[11px] text-zinc-400 leading-relaxed">
                  In live racing, a 7.00 outsider like <em>Secret Tactic</em> has a ~15% true statistical chance to win when the leaders exhaust themselves upfront. Switch to <strong>Monte Carlo Mode</strong> to see stochastic realities where underdogs swoop in!
                </p>
              </div>
            </div>

            <div className="pt-2 border-t border-zinc-800/80 text-[10px] text-zinc-500">
              * Length conversions: 1 horse length $\approx$ 2.4 metres or ~0.17 seconds of sprint elapsed time.
            </div>
          </div>

        </div>

      </div>

    </div>
  );
};
