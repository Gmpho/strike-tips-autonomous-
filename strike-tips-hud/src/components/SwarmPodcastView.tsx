import React, { useState, useEffect, useRef } from 'react';
import {
  Radio,
  Play,
  Pause,
  RotateCcw,
  Sparkles,
  Volume2,
  VolumeX,
  FastForward,
  Loader2,
  Headphones,
  CheckCircle2,
  Calendar,
  Layers,
  Flame,
  Award,
} from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../hooks/useHUD';
import { apiFetch } from '../lib/api-fetch';

export interface SwarmAgentDialogue {
  speaker: 'host' | 'analyst' | 'stats' | 'scout';
  speakerName: string;
  roleTitle: string;
  voice: 'Kore' | 'Puck' | 'Charon' | 'Fenrir' | 'Zephyr';
  avatar: string;
  text: string;
  audioUrl?: string;
}

export interface PodcastEpisode {
  id: string;
  title: string;
  track: string;
  raceFocus: string;
  headline: string;
  durationEst: string;
  timestamp: string;
  dialogue: SwarmAgentDialogue[];
  summary: string[];
}

const DEFAULT_EPISODE: PodcastEpisode = {
  id: 'pod-live-01',
  title: 'Kenilworth Feature Roundtable: Firealley Edge & Banker Breakdown',
  track: 'Kenilworth',
  raceFocus: 'Race 7 (Pinnacle Stakes)',
  headline: 'Autonomous 4-agent swarm consensus confirms an 8.4% Bayesian edge on Firealley over market favourite Gimme A Prince.',
  durationEst: '3m 12s',
  timestamp: 'Live Trackside',
  summary: [
    'Firealley holds +8.4% model edge against market opening price of 4.2',
    'Middle draw (Stall 4) offers tactical run into Kenilworth straight',
    'Kelly Governor allocates conservative 2.5% half-Kelly staking bankroll',
  ],
  dialogue: [
    {
      speaker: 'host',
      speakerName: 'Sipho Ndlovu',
      roleTitle: 'Lead Paddock Presenter',
      voice: 'Kore',
      avatar: '🎙️',
      text: "Welcome trackside to the Strike Swarm Racing Podcast! We are locked onto Race 7 at Kenilworth. The betting exchanges are turbulent, and our multi-agent model pipeline has flagged an extraordinary edge. Gareth, what is your turn-of-foot model revealing?",
    },
    {
      speaker: 'analyst',
      speakerName: 'Gareth Vance',
      roleTitle: 'Senior Form & Speed Analyst',
      voice: 'Charon',
      avatar: '🏇',
      text: "Sipho, look closely at Firealley in stall four. He clocked the fastest final 400m sectional over course and distance last month. The market is over-weighting Gimme A Prince carrying top weight on good-to-soft turf.",
    },
    {
      speaker: 'stats',
      speakerName: 'Dr. Elena Becker',
      roleTitle: 'Bayesian Edge & Kelly Modeler',
      voice: 'Zephyr',
      avatar: '📊',
      text: "Mathematically, the market implies a 23.8% win rate at 4.2 odds. Our Bayesian Monte Carlo simulation scores Firealley at 32.2%. That gives us a clean 8.4% positive edge — triggering a half-Kelly stake allocation.",
    },
    {
      speaker: 'scout',
      speakerName: 'Tebogo Molefe',
      roleTitle: 'Trackside Scout & Going Reporter',
      voice: 'Puck',
      avatar: '🔍',
      text: "Paddock check confirms Elena's numbers. Firealley is walking calmly, coat is gleaming with zero pre-race agitation, and the rail is running true. He's primed for a massive effort.",
    },
    {
      speaker: 'host',
      speakerName: 'Sipho Ndlovu',
      roleTitle: 'Lead Paddock Presenter',
      voice: 'Kore',
      avatar: '🎙️',
      text: "Superb consensus from the swarm. For all exotic players, Firealley acts as our prime Pick 6 banker, with Silver Operator as the high-odds multiplier. Let's send it to the stalls!",
    },
  ],
};

const SWARM_BADGES: Record<string, { color: string; border: string; bg: string }> = {
  host: { color: 'text-purple-400', border: 'border-purple-500/40', bg: 'bg-purple-500/10' },
  analyst: { color: 'text-amber-400', border: 'border-amber-500/40', bg: 'bg-amber-500/10' },
  stats: { color: 'text-emerald-400', border: 'border-emerald-500/40', bg: 'bg-emerald-500/10' },
  scout: { color: 'text-cyan-400', border: 'border-cyan-500/40', bg: 'bg-cyan-500/10' },
  gemma: { color: 'text-pink-400', border: 'border-pink-500/40', bg: 'bg-pink-500/10' },
};

const FALLBACK_PRESETS: Array<{
  id: string;
  course: string;
  raceNumber: string;
  t: string;
  distance_m: number;
  runners: any[];
  complexity?: 'LOW_RISK' | 'MEDIUM_RISK' | 'HIGH_RISK';
  dsi?: number;
}> = [
  {
    id: 'preset-kenilworth-r7',
    course: 'Kenilworth',
    raceNumber: '7',
    t: '15:45',
    distance_m: 1600,
    complexity: 'MEDIUM_RISK',
    dsi: 1.0,
    runners: [
      { name: 'Firealley', odds: 4.2, edge: 8.4, form: '1-2-1', draw: 4, jockeyName: 'R. Fourie', trainerName: 'J. Snaith', gear: 'Blinkers' },
      { name: 'Master Archie', odds: 6.5, edge: 6.1, form: '3-1-4', draw: 1, jockeyName: 'C. Zackey', trainerName: 'P. Peter' },
      { name: 'Gimme A Prince', odds: 2.8, edge: -1.2, form: '1-1-2', draw: 8, jockeyName: 'K. de Melo', trainerName: 'D. Kannemeyer' },
      { name: 'Silver Operator', odds: 14.0, edge: 3.5, form: '5-4-3', draw: 11, jockeyName: 'G. van Niekerk', trainerName: 'V. Marshall', gear: 'Pacifiers' },
    ],
  },
  {
    id: 'preset-greyville-r4',
    course: 'Greyville',
    raceNumber: '4',
    t: '14:10',
    distance_m: 1200,
    complexity: 'LOW_RISK',
    dsi: 0.75,
    runners: [
      { name: 'Gladatorian', odds: 3.5, edge: 7.2, form: '2-1-1', draw: 2, jockeyName: 'S. Khumalo', trainerName: 'S. Tarry' },
      { name: 'Coin Spinner', odds: 5.0, edge: 4.8, form: '1-4-2', draw: 5, jockeyName: 'A. Mgudlwa', trainerName: 'T. Rivalland' },
      { name: 'Sun Blushed', odds: 8.0, edge: 5.1, form: '3-2-3', draw: 7, jockeyName: 'R. Venniker', trainerName: 'M. Roberts' },
    ],
  },
  {
    id: 'preset-turffontein-r6',
    course: 'Turffontein',
    raceNumber: '6',
    t: '15:20',
    distance_m: 1160,
    complexity: 'HIGH_RISK',
    dsi: 1.25,
    runners: [
      { name: 'Main Defender', odds: 2.1, edge: 9.5, form: '1-1-1', draw: 3, jockeyName: 'C. Maujean', trainerName: 'T. Peter' },
      { name: 'Thunderstruck', odds: 4.8, edge: 5.0, form: '2-1-3', draw: 6, jockeyName: 'P. Strydom', trainerName: 'S. Tarry' },
      { name: 'Rulership', odds: 11.0, edge: 3.2, form: '4-3-1', draw: 9, jockeyName: 'K. Matsunyane', trainerName: 'M. de Kock' },
    ],
  },
];

export const SwarmPodcastView: React.FC = () => {
  const state = useHUD();
  const [episode, setEpisode] = useState<PodcastEpisode>(DEFAULT_EPISODE);
  const [currentLineIndex, setCurrentLineIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isSynthesizing, setIsSynthesizing] = useState<boolean>(false);
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [muted, setMuted] = useState<boolean>(false);
  const [selectedEngine, setSelectedEngine] = useState<'gemini' | 'groq' | 'gemma4'>('gemma4');
  const [errorNote, setErrorNote] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const audioCacheRef = useRef<Map<number, string>>(new Map());
  const inFlightFetches = useRef<Map<number, Promise<string | null>>>(new Map());

  // Collect live races from HUD state or fall back to verified presets
  const rawRaces = Object.values(state.events || {});
  const displayRaces = rawRaces.length > 0 ? rawRaces : FALLBACK_PRESETS;
  const [selectedRaceId, setSelectedRaceId] = useState<string>(() => displayRaces[0]?.id || 'preset-kenilworth-r7');

  // Resolve currently active race and its deep metadata
  const activeRace = displayRaces.find(r => (r.id || `${r.course}-${r.raceNumber}`) === selectedRaceId) || displayRaces[0];
  const courseName = activeRace?.course || 'Kenilworth';
  const raceNum = activeRace?.raceNumber ? `Race ${activeRace.raceNumber}` : 'Race 7';
  const distanceM = activeRace?.distance_m;
  const raceTime = activeRace?.t;
  const runnerCount = activeRace?.runners?.length || 0;
  const topEdgeRunner = (activeRace?.runners || []).slice().sort((a, b) => (Number(b.edge) || 0) - (Number(a.edge) || 0))[0];

  const currentDialogue = episode.dialogue[currentLineIndex];

  // Stop audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
    };
  }, []);

  // Proactive lookahead audio fetcher with in-flight deduplication
  const fetchLineAudio = (lineIdx: number): Promise<string | null> => {
    if (lineIdx < 0 || lineIdx >= episode.dialogue.length) return Promise.resolve(null);
    if (audioCacheRef.current.has(lineIdx)) {
      return Promise.resolve(audioCacheRef.current.get(lineIdx)!);
    }
    if (inFlightFetches.current.has(lineIdx)) {
      return inFlightFetches.current.get(lineIdx)!;
    }

    const line = episode.dialogue[lineIdx];
    const promise = (async () => {
      try {
        const res = await apiFetch('/api/podcast/synthesize-line', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            text: line.text,
            voice: line.voice,
          }),
        });

        if (!res.ok) {
          throw new Error('TTS service returned non-200');
        }

        const blob = await res.blob();
        const audioUrl = URL.createObjectURL(blob);
        audioCacheRef.current.set(lineIdx, audioUrl);
        return audioUrl;
      } catch (err) {
        console.warn(`[Podcast Audio Pre-fetch failed line ${lineIdx}]`, err);
        return null;
      } finally {
        inFlightFetches.current.delete(lineIdx);
      }
    })();

    inFlightFetches.current.set(lineIdx, promise);
    return promise;
  };

  // Background lookahead: pre-synthesize the next 2 lines while current is speaking
  const prefetchUpcomingLines = (currentIdx: number) => {
    if (currentIdx + 1 < episode.dialogue.length) {
      void fetchLineAudio(currentIdx + 1);
    }
    if (currentIdx + 2 < episode.dialogue.length) {
      void fetchLineAudio(currentIdx + 2);
    }
  };

  // Pre-fetch opening lines eagerly on new episode
  useEffect(() => {
    if (episode.dialogue.length > 0) {
      void fetchLineAudio(0);
      if (episode.dialogue.length > 1) {
        void fetchLineAudio(1);
      }
    }
  }, [episode]);

  // Play dialogue line audio with 0ms buffering gap
  const playLineAudio = async (lineIdx: number) => {
    if (lineIdx < 0 || lineIdx >= episode.dialogue.length) {
      setIsPlaying(false);
      return;
    }

    const line = episode.dialogue[lineIdx];
    setCurrentLineIndex(lineIdx);

    // Immediately kick off background lookahead for upcoming lines
    prefetchUpcomingLines(lineIdx);

    try {
      let audioUrl = audioCacheRef.current.get(lineIdx);

      if (!audioUrl) {
        setIsSynthesizing(true);
        audioUrl = (await fetchLineAudio(lineIdx)) || undefined;
        setIsSynthesizing(false);
      }

      if (!audioUrl) {
        throw new Error('No audio URL available for line ' + lineIdx);
      }

      if (!audioRef.current) {
        audioRef.current = new Audio();
      }

      audioRef.current.src = audioUrl;
      audioRef.current.muted = muted;

      audioRef.current.onended = () => {
        if (lineIdx + 1 < episode.dialogue.length) {
          // Plays next line immediately from lookahead cache!
          void playLineAudio(lineIdx + 1);
        } else {
          setIsPlaying(false);
          setCurrentLineIndex(0);
        }
      };

      await audioRef.current.play();
      setIsPlaying(true);
    } catch (err: any) {
      console.warn('[Podcast Audio Fallback]', err);
      setIsSynthesizing(false);
      // If voice audio generation fails (e.g. no GEMINI_API_KEY in dev sandbox),
      // simulate natural pacing so dialogue advances automatically.
      const simulatedDurationMs = Math.max(3000, line.text.length * 55);
      const timer = window.setTimeout(() => {
        if (lineIdx + 1 < episode.dialogue.length) {
          void playLineAudio(lineIdx + 1);
        } else {
          setIsPlaying(false);
          setCurrentLineIndex(0);
        }
      }, simulatedDurationMs);

      return () => clearTimeout(timer);
    }
  };

  const togglePlayback = () => {
    if (isPlaying) {
      if (audioRef.current) audioRef.current.pause();
      setIsPlaying(false);
    } else {
      playLineAudio(currentLineIndex);
    }
  };

  const handleSkipNext = () => {
    if (audioRef.current) audioRef.current.pause();
    const nextIdx = Math.min(episode.dialogue.length - 1, currentLineIndex + 1);
    playLineAudio(nextIdx);
  };

  const handleRestart = () => {
    if (audioRef.current) audioRef.current.pause();
    audioCacheRef.current.clear();
    setCurrentLineIndex(0);
    playLineAudio(0);
  };

  // Generate new episode on chosen live race with live runners & full form context
  const handleGenerateEpisode = async () => {
    setIsGenerating(true);
    setErrorNote(null);
    if (audioRef.current) {
      audioRef.current.pause();
      setIsPlaying(false);
    }
    audioCacheRef.current.clear();

    const runnersPayload = (activeRace?.runners || []).map(r => ({
      name: r.name,
      odds: r.odds,
      edge: typeof r.edge === 'number' ? r.edge : (r.edge ? parseFloat(String(r.edge)) : undefined),
      form: r.form,
      jockey: r.jockeyName,
      trainer: r.trainerName,
      draw: r.draw,
      gear: r.gear,
      daysSinceRun: r.daysSinceRun,
    }));

    try {
      const res = await apiFetch('/api/podcast/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          track: courseName,
          raceNumber: raceNum,
          distanceM: distanceM,
          raceTime: raceTime,
          complexity: activeRace?.complexity,
          dsi: activeRace?.dsi,
          engine: selectedEngine,
          runners: runnersPayload,
        }),
      });

      if (!res.ok) {
        throw new Error(`Failed to generate episode: ${res.statusText}`);
      }

      const freshEpisode: PodcastEpisode = await res.json();
      setEpisode(freshEpisode);
      setCurrentLineIndex(0);
      setIsPlaying(false);
    } catch (err: any) {
      console.error('[Podcast Generation Failed]', err);
      setErrorNote(err.message || 'Generation failed. Check server connection.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6 w-full max-w-6xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="relative overflow-hidden rounded-3xl bg-linear-to-br from-[#120826] via-[#0d071a] to-black border border-purple-500/20 p-6 sm:p-8 shadow-2xl">
        <div className="absolute top-0 right-0 w-96 h-96 bg-purple-600/10 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-0 left-0 w-80 h-80 bg-emerald-600/10 rounded-full blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col md:flex-row md:items-center justify-between gap-6">
          <div className="flex flex-col gap-2 max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-full bg-purple-500/20 border border-purple-500/30 text-purple-300 text-xs font-black uppercase tracking-wider flex items-center gap-1.5">
                <Radio className="w-3.5 h-3.5 animate-pulse text-purple-400" />
                Autonomous Swarm Podcast
              </span>
              <span className="px-2 py-0.5 rounded-md bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-[10px] font-black uppercase">
                Live Turf Intelligence
              </span>
            </div>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-black text-white tracking-tight">
              The Strike Swarm Roundtable
            </h1>
            <p className="text-sm text-theme-secondary leading-relaxed">
              Real-time thoroughbred podcast featuring 5 autonomous racing specialists: Paddock Anchor,
              Form Analyst, Bayesian Edge Modeler, Trackside Scout, and Gemma AI analyzing live South African turf.
            </p>
          </div>

          {/* Episode Control Actions */}
          <div className="flex flex-wrap sm:flex-nowrap items-center gap-3 shrink-0">
            <select
              value={selectedRaceId}
              onChange={(e) => setSelectedRaceId(e.target.value)}
              className="bg-black/60 border border-purple-500/30 rounded-2xl px-3 py-3 text-sm text-white font-bold focus:outline-none focus:ring-2 focus:ring-purple-500/50 min-h-[48px] max-w-[280px] sm:max-w-xs truncate"
              aria-label="Select live race for podcast preview"
            >
              {displayRaces.map((r) => {
                const id = r.id || `${r.course}-${r.raceNumber}`;
                const dist = r.distance_m ? `${r.distance_m}m` : '';
                const time = r.t ? `@ ${r.t}` : '';
                const count = r.runners?.length ? `${r.runners.length} runners` : '';
                return (
                  <option key={id} value={id} className="bg-[#0c0817] text-white">
                    🏇 {r.course} · Race {r.raceNumber || '1'} {time} {dist ? `(${dist})` : ''} {count ? `· ${count}` : ''}
                  </option>
                );
              })}
            </select>

            <select
              value={selectedEngine}
              onChange={(e) => setSelectedEngine(e.target.value as any)}
              className="bg-black/60 border border-purple-500/30 rounded-2xl px-3 py-3 text-sm text-purple-200 font-bold focus:outline-none focus:ring-2 focus:ring-purple-500/50 min-h-[48px]"
              aria-label="Select podcast scriptwriter engine"
            >
              <option value="gemma4" className="bg-[#0c0817]">🧠 Gemma 4 (Google AI Studio · 1.5k Free)</option>
              <option value="groq" className="bg-[#0c0817]">⚡ Groq LPU (Ultra-Fast ~800ms)</option>
              <option value="gemini" className="bg-[#0c0817]">✨ Gemini 3.5 Flash (Search Grounded)</option>
            </select>

            <button
              onClick={handleGenerateEpisode}
              disabled={isGenerating}
              className="px-5 py-3 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white font-black text-sm tracking-wide transition-all shadow-lg shadow-purple-600/30 flex items-center gap-2 disabled:opacity-50 min-h-[48px]"
            >
              {isGenerating ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Synthesizing Swarm...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4" />
                  <span>Generate Episode</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Live Race Targeted Status Strip */}
        <div className="mt-4 pt-4 border-t border-purple-500/20 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="px-2.5 py-0.5 rounded-full bg-red-500/20 border border-red-500/40 text-red-300 font-black uppercase text-[10px] flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
              LIVE RACE TARGETED
            </span>
            <span className="text-white font-black text-sm">
              {courseName} · {raceNum}
            </span>
            {raceTime && (
              <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-slate-300">
                Post: <strong className="text-white">{raceTime} CAT</strong>
              </span>
            )}
            {distanceM && (
              <span className="px-2 py-0.5 rounded-md bg-purple-500/15 border border-purple-500/30 text-purple-200">
                {distanceM}m {distanceM <= 1200 ? 'Sprint' : distanceM <= 1600 ? 'Mile' : 'Route'}
              </span>
            )}
            <span className="px-2 py-0.5 rounded-md bg-emerald-500/15 border border-emerald-500/30 text-emerald-300 font-bold">
              {runnerCount} Runners in Field
            </span>
            {activeRace?.dsi !== undefined && (
              <span className="px-2 py-0.5 rounded-md bg-amber-500/15 border border-amber-500/30 text-amber-300 font-mono">
                DSI: {activeRace.dsi.toFixed(2)}x
              </span>
            )}
          </div>

          {topEdgeRunner && Number(topEdgeRunner.edge) > 0 && (
            <div className="flex items-center gap-1.5 text-xs bg-emerald-950/50 border border-emerald-500/40 px-3 py-1 rounded-xl">
              <span className="text-emerald-400 font-bold">Top Value:</span>
              <span className="text-white font-black">{topEdgeRunner.name}</span>
              <span className="px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 font-black">
                +{topEdgeRunner.edge}% Edge
              </span>
            </div>
          )}
        </div>

        {errorNote && (
          <div className="mt-4 p-3 rounded-xl bg-red-500/20 border border-red-500/30 text-xs text-red-200 font-bold">
            {errorNote}
          </div>
        )}
      </div>

      {/* Main Player & Live Dialogue Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Player Console & Swarm Roster */}
        <div className="lg:col-span-5 flex flex-col gap-6">
          {/* Master Episode Player Card */}
          <div className="rounded-3xl bg-theme-panel/90 border border-theme p-6 flex flex-col gap-5 shadow-xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4">
              <div className="flex items-center gap-2 text-xs font-bold text-theme-secondary">
                <Calendar className="w-3.5 h-3.5 text-purple-400" />
                <span>{episode.track} · {episode.raceFocus}</span>
              </div>
              <span className="text-xs font-mono font-bold text-emerald-400 flex items-center gap-1">
                <Flame className="w-3.5 h-3.5 fill-emerald-400" />
                Est. {episode.durationEst}
              </span>
            </div>

            <div className="flex flex-col gap-1.5">
              <h2 className="text-lg font-black text-white leading-snug">
                {episode.title}
              </h2>
              <p className="text-xs text-theme-secondary line-clamp-2">
                {episode.headline}
              </p>
            </div>

            {/* Visual Waveform / Speaker Status */}
            <div className="p-4 rounded-2xl bg-black/50 border border-white/5 flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                  <span className="text-2xl">{currentDialogue?.avatar || '🎙️'}</span>
                  <div>
                    <div className="text-xs font-black text-white">
                      {currentDialogue?.speakerName}
                    </div>
                    <div className="text-[10px] text-theme-secondary uppercase tracking-wider">
                      {currentDialogue?.roleTitle}
                    </div>
                  </div>
                </div>

                {isPlaying && (
                  <div className="flex items-center gap-1 h-4">
                    {[0.6, 1, 0.4, 0.9, 0.7].map((_, i) => (
                      <motion.div
                        key={i}
                        className="w-1 bg-purple-400 rounded-full"
                        animate={{ height: ['4px', '16px', '4px'] }}
                        transition={{ repeat: Infinity, duration: 0.8, delay: i * 0.15 }}
                      />
                    ))}
                  </div>
                )}
              </div>

              {/* Progress Bar */}
              <div className="w-full bg-white/10 rounded-full h-1.5 overflow-hidden mt-1">
                <motion.div
                  className="bg-linear-to-r from-purple-500 to-emerald-400 h-full rounded-full"
                  animate={{
                    width: `${((currentLineIndex + 1) / episode.dialogue.length) * 100}%`,
                  }}
                  transition={{ duration: 0.3 }}
                />
              </div>
              <div className="flex justify-between text-[10px] font-mono text-theme-secondary">
                <span>Turn {currentLineIndex + 1} of {episode.dialogue.length}</span>
                <span>{isSynthesizing ? 'Buffering voice...' : isPlaying ? 'Broadcasting' : 'Ready'}</span>
              </div>
            </div>

            {/* Playback Controls */}
            <div className="flex items-center justify-between pt-1">
              <button
                onClick={() => setMuted(!muted)}
                aria-label={muted ? "Unmute podcast" : "Mute podcast"}
                className="p-3 rounded-2xl bg-white/5 border border-white/10 text-theme-secondary hover:text-white transition-all"
              >
                {muted ? <VolumeX className="w-4 h-4 text-red-400" /> : <Volume2 className="w-4 h-4" />}
              </button>

              <div className="flex items-center gap-3">
                <button
                  onClick={handleRestart}
                  aria-label="Restart episode"
                  title="Restart episode from beginning"
                  className="p-3 rounded-2xl bg-white/5 border border-white/10 text-theme-secondary hover:text-white transition-all active:scale-95"
                >
                  <RotateCcw className="w-4 h-4" />
                </button>

                <button
                  onClick={togglePlayback}
                  disabled={isSynthesizing}
                  aria-label={isPlaying ? "Pause podcast" : "Play podcast"}
                  className="w-14 h-14 rounded-2xl bg-purple-600 hover:bg-purple-500 text-white flex items-center justify-center transition-all shadow-lg shadow-purple-600/40 active:scale-95"
                >
                  {isSynthesizing ? (
                    <Loader2 className="w-6 h-6 animate-spin" />
                  ) : isPlaying ? (
                    <Pause className="w-6 h-6 fill-white" />
                  ) : (
                    <Play className="w-6 h-6 fill-white ml-0.5" />
                  )}
                </button>

                <button
                  onClick={handleSkipNext}
                  aria-label="Next speaker turn"
                  title="Skip to next speaker"
                  className="p-3 rounded-2xl bg-white/5 border border-white/10 text-theme-secondary hover:text-white transition-all active:scale-95"
                >
                  <FastForward className="w-4 h-4" />
                </button>
              </div>

              <div className="p-3 rounded-2xl bg-white/5 border border-white/10 text-purple-400">
                <Headphones className="w-4 h-4" />
              </div>
            </div>
          </div>

          {/* Episode Intelligence Consensus Points */}
          <div className="rounded-3xl bg-theme-panel/70 border border-theme p-6 flex flex-col gap-4">
            <div className="flex items-center gap-2 text-xs font-black uppercase tracking-wider text-purple-400">
              <Award className="w-4 h-4" />
              <span>Swarm Verdict Consensus</span>
            </div>
            <div className="flex flex-col gap-2.5">
              {episode.summary.map((point, i) => (
                <div key={i} className="flex items-start gap-2.5 text-xs text-theme-secondary leading-relaxed">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                  <span>{point}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Autonomous Cast Roster Info */}
          <div className="rounded-3xl bg-theme-panel/50 border border-theme p-5 flex flex-col gap-3">
            <div className="text-[11px] font-black uppercase tracking-wider text-theme-secondary">
              Swarm Specialists Cast
            </div>
            <div className="grid grid-cols-2 gap-2.5">
              {[
                { name: 'Sipho Ndlovu', role: 'Presenter', voice: 'Gemini Kore', color: 'border-purple-500/30' },
                { name: 'Gareth Vance', role: 'Form Analyst', voice: 'Gemini Charon', color: 'border-amber-500/30' },
                { name: 'Dr. Elena Becker', role: 'Bayesian Edge', voice: 'Gemini Zephyr', color: 'border-emerald-500/30' },
                { name: 'Tebogo Molefe', role: 'Track Scout', voice: 'Gemini Puck', color: 'border-cyan-500/30' },
              ].map((c, idx) => (
                <div key={idx} className={`p-2.5 rounded-xl bg-black/40 border ${c.color} flex flex-col gap-0.5`}>
                  <span className="text-xs font-bold text-white truncate">{c.name}</span>
                  <span className="text-[10px] text-theme-secondary truncate">{c.role}</span>
                  <span className="text-[9px] font-mono text-purple-400/80">{c.voice}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Live Broadcast Interactive Transcript */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="flex items-center justify-between px-2">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-purple-400" />
              <h3 className="text-sm font-black text-white uppercase tracking-wider">
                Live Broadcast Script
              </h3>
            </div>
            <span className="text-xs font-mono text-theme-secondary">
              Click any turn to listen
            </span>
          </div>

          <div className="flex flex-col gap-3 max-h-[680px] overflow-y-auto pr-1 custom-scrollbar">
            {episode.dialogue.map((turn, idx) => {
              const isTurnActive = idx === currentLineIndex;
              const badge = SWARM_BADGES[turn.speaker] || SWARM_BADGES.host;

              return (
                <motion.div
                  key={idx}
                  onClick={() => playLineAudio(idx)}
                  className={`p-4 sm:p-5 rounded-2xl border transition-all cursor-pointer relative overflow-hidden ${
                    isTurnActive
                      ? 'bg-purple-900/25 border-purple-500/60 shadow-lg shadow-purple-500/10 ring-1 ring-purple-500/40'
                      : 'bg-theme-panel/70 border-theme hover:bg-theme-panel hover:border-purple-500/30'
                  }`}
                  whileHover={{ scale: 1.005 }}
                  transition={{ duration: 0.15 }}
                >
                  {isTurnActive && (
                    <div className="absolute top-0 left-0 bottom-0 w-1 bg-purple-500 animate-pulse" />
                  )}

                  <div className="flex items-start gap-3.5">
                    <span className="text-2xl shrink-0 select-none mt-0.5">{turn.avatar}</span>
                    <div className="flex flex-col gap-1 flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <div className="flex items-center gap-2 min-w-0">
                          <span className="text-xs font-black text-white truncate">
                            {turn.speakerName}
                          </span>
                          <span className={`px-2 py-0.2 rounded-md text-[9px] font-black uppercase tracking-wider ${badge.bg} ${badge.color} border ${badge.border}`}>
                            {turn.roleTitle}
                          </span>
                        </div>
                        <span className="text-[10px] font-mono text-theme-secondary opacity-70">
                          {turn.voice}
                        </span>
                      </div>

                      <p className={`text-xs sm:text-sm leading-relaxed mt-1 ${
                        isTurnActive ? 'text-purple-100 font-medium' : 'text-theme-secondary'
                      }`}>
                        "{turn.text}"
                      </p>
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
