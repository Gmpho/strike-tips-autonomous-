import React, { useMemo } from 'react';
import { Radar, Newspaper, Sparkles, Scale, Radio, Clock, ExternalLink, Tag } from 'lucide-react';
import { motion } from 'framer-motion';
import { useHUD } from '../../hooks/useHUD';
import { linkStoriesToRaces } from '../../lib/race-story-link';

interface EngineMeta {
  key: string;
  label: string;
  icon: React.ReactNode;
  dot: string;
  badge: string;
  cardBorder: string;
  desc: string;
}

const ENGINES: EngineMeta[] = [
  {
    key: 'swarm',
    label: 'Swarm Researcher',
    icon: <Radar className="w-4 h-4 text-emerald-400" />,
    dot: 'bg-emerald-500',
    badge: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
    cardBorder: 'hover:border-emerald-500/40',
    desc: 'Form insights for all regions',
  },
  {
    key: 'news',
    label: 'News RAG',
    icon: <Newspaper className="w-4 h-4 text-cyan-400" />,
    dot: 'bg-cyan-500',
    badge: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
    cardBorder: 'hover:border-cyan-500/40',
    desc: 'Free feeds → learning memory',
  },
  {
    key: 'dream',
    label: 'Dreaming Engine',
    icon: <Sparkles className="w-4 h-4 text-purple-400" />,
    dot: 'bg-purple-500',
    badge: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
    cardBorder: 'hover:border-purple-500/40',
    desc: 'Scenario simulations (DSI)',
  },
  {
    key: 'governor',
    label: 'Governor',
    icon: <Scale className="w-4 h-4 text-amber-400" />,
    dot: 'bg-amber-500',
    badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
    cardBorder: 'hover:border-amber-500/40',
    desc: 'Risk gate · Kelly × DSI staking',
  },
];

function fmtClock(ts: number): string {
  const d = new Date(ts * 1000);
  return isNaN(d.getTime()) ? '' : d.toLocaleTimeString('en-GB', { hour12: false });
}

function fmtRelative(ts: number): string {
  const diffMs = Date.now() - ts * 1000;
  if (diffMs < 0 || isNaN(diffMs)) return '';
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return 'just now';
  if (mins === 1) return '1 min ago';
  if (mins < 60) return `${mins} mins ago`;
  const hrs = Math.floor(mins / 60);
  return hrs === 1 ? '1 hr ago' : `${hrs} hrs ago`;
}

function EngineCard({ meta, lastEvent }: { meta: EngineMeta; lastEvent?: { message: string; ts: number } }) {
  const active = Boolean(lastEvent);
  return (
    <div className={`rounded-2xl bg-theme-panel border border-theme p-4 transition-all duration-200 ${active ? meta.cardBorder : ''}`}>
      <div className="flex items-center justify-between gap-2 mb-1.5">
        <div className="flex items-center gap-2 min-w-0">
          {meta.icon}
          <span className="text-sm font-black text-theme-primary truncate">{meta.label}</span>
        </div>
        {active ? (
          <span className={`shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[8px] font-black uppercase tracking-wider ${meta.badge}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${meta.dot} animate-pulse`} />
            Active
          </span>
        ) : (
          <span className="shrink-0 inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border border-white/10 bg-white/5 text-slate-500 text-[8px] font-black uppercase tracking-wider">
            Idle
          </span>
        )}
      </div>
      <p className="text-[9px] font-bold text-theme-secondary uppercase tracking-wider mb-2">{meta.desc}</p>
      {active ? (
        <div>
          <p className="text-[11px] font-semibold text-slate-300 leading-snug line-clamp-2" title={lastEvent!.message}>
            {lastEvent!.message}
          </p>
          <p className="flex items-center gap-1 mt-1.5 text-[9px] font-bold text-theme-secondary/60 uppercase tracking-wider">
            <Clock className="w-2.5 h-2.5" />
            {fmtRelative(lastEvent!.ts)}
          </p>
        </div>
      ) : (
        <p className="text-[11px] text-slate-600 font-medium">Awaiting first cycle…</p>
      )}
    </div>
  );
}

export const TelemetryView: React.FC = () => {
  const { telemetry, events, news } = useHUD();

  // Live races that news actually mentions (course or runner name). The
  // backend links news -> racecards in Chroma (swarm_researcher) and emits
  // a 🏷️ count into telemetry; this surfaces WHICH story belongs to WHICH
  // race, with a link to the article.
  const racesWithStories = useMemo(
    () => linkStoriesToRaces(Object.values(events || {}), news || []),
    [events, news],
  );
  const liveRaceCount = Object.keys(events || {}).length;

  // Latest event per engine
  const latestByEngine = useMemo(() => {
    const map: Record<string, { message: string; ts: number }> = {};
    (telemetry || []).forEach((t) => {
      if (!map[t.engine]) map[t.engine] = { message: t.message, ts: t.ts };
    });
    return map;
  }, [telemetry]);

  const anyActive = ENGINES.some((e) => latestByEngine[e.key]);

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98, y: 10 }}
      animate={{ opacity: 1, scale: 1, y: 0 }}
      transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
      className="p-3.5 sm:p-6 space-y-4 sm:space-y-6 w-full flex flex-col min-h-0"
    >
      {/* Header */}
      <div className="shrink-0">
        <h2 className="text-2xl font-bold bg-gradient-to-r from-emerald-400 to-cyan-500 bg-clip-text text-transparent">
          Live Ops
        </h2>
        <p className="text-xs text-theme-secondary mt-1 font-semibold">
          Agents in action — real-time engine telemetry streamed over SSE
        </p>
      </div>

      {/* Engine cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        {ENGINES.map((meta) => (
          <EngineCard key={meta.key} meta={meta} lastEvent={latestByEngine[meta.key]} />
        ))}
      </div>

      {/* Live races ⨯ news stories */}
      <div className="shrink-0">
        <div className="flex items-center gap-2 mb-3">
          <Tag className="w-3.5 h-3.5 text-theme-secondary" />
          <h3 className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
            Live Races ⨯ Stories
          </h3>
          <div className="flex-1 h-px bg-theme" />
          <span className="text-[9px] font-black text-cyan-500/70 bg-cyan-500/10 px-2 py-0.5 rounded-full border border-cyan-500/20 tabular">
            {liveRaceCount} race{liveRaceCount === 1 ? '' : 's'} live · {racesWithStories.length} linked
          </span>
        </div>

        {racesWithStories.length === 0 ? (
          <div className="rounded-2xl bg-theme-panel border border-theme px-4 py-5 text-center">
            <p className="text-[11px] font-bold text-theme-primary/70">
              {liveRaceCount === 0
                ? 'No live races in the card right now'
                : 'No live race is named in the current headlines yet'}
            </p>
            <p className="text-[10px] text-theme-secondary mt-1">
              {liveRaceCount === 0
                ? 'The odds monitor syncs the card every 5 minutes — races appear here as soon as they are on.'
                : 'Stories appear here the moment a headline mentions one of today’s tracks or runners.'}
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-2 max-h-[340px] overflow-y-auto custom-scrollbar scroll-container pr-1">
            {racesWithStories.map((race) => (
              <motion.div
                key={race.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                className="rounded-2xl bg-theme-panel border border-theme px-3 py-2.5 hover:border-cyan-500/30 transition-colors"
              >
                <div className="flex items-center gap-2 mb-1.5">
                  <span className="text-[11px] font-black text-theme-primary uppercase tracking-tight truncate">
                    {race.course} R{race.raceNumber}
                  </span>
                  {race.offTime && (
                    <span className="text-[9px] font-mono text-theme-secondary shrink-0">{race.offTime}</span>
                  )}
                  <span className="text-[9px] font-mono text-theme-secondary/70 shrink-0">
                    {race.runnerCount} run
                  </span>
                </div>
                <div className="space-y-1">
                  {race.stories.map((story, idx) => {
                    const chip = (
                      <>
                        <Tag className="w-3 h-3 shrink-0 text-cyan-400/80" />
                        <span className="text-[10px] font-semibold text-theme-primary leading-snug line-clamp-2 min-w-0">
                          {story.title}
                        </span>
                        <ExternalLink className="w-3 h-3 shrink-0 text-theme-secondary/60" />
                      </>
                    );
                    return story.url ? (
                      <a
                        key={story.id || `${race.id}-${idx}`}
                        href={story.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        title={`Linked via “${story.matchedOn}”${story.source ? ` · ${story.source}` : ''}`}
                        className="flex items-start gap-1.5 px-2 py-1.5 rounded-lg bg-cyan-500/5 border border-cyan-500/15 hover:bg-cyan-500/10 hover:border-cyan-500/30 transition-colors"
                      >
                        {chip}
                      </a>
                    ) : (
                      <div
                        key={story.id || `${race.id}-${idx}`}
                        title={`Linked via “${story.matchedOn}”`}
                        className="flex items-start gap-1.5 px-2 py-1.5 rounded-lg bg-cyan-500/5 border border-cyan-500/15"
                      >
                        {chip}
                      </div>
                    );
                  })}
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Activity log */}
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="flex items-center gap-2 mb-3">
          <Radio className="w-3.5 h-3.5 text-theme-secondary" />
          <h3 className="text-[10px] font-black text-theme-secondary uppercase tracking-widest">
            Activity Stream
          </h3>
          <div className="flex-1 h-px bg-theme" />
          <span className="text-[9px] font-black text-emerald-500/70 bg-emerald-500/10 px-2 py-0.5 rounded-full border border-emerald-500/20">
            LIVE
          </span>
        </div>

        {!anyActive ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="p-8 rounded-3xl bg-white/5 border border-white/10 text-center max-w-xs">
              <Radar className="w-12 h-12 mx-auto opacity-30 text-theme-secondary" />
              <p className="mt-4 text-sm font-bold text-theme-primary/60">No engine activity yet</p>
              <p className="mt-1 text-xs text-theme-secondary leading-relaxed">
                The Swarm Researcher cycles every 10 minutes and the Dream heartbeat every 5.
                Events will stream here automatically.
              </p>
            </div>
          </div>
        ) : (
          <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar scroll-container pr-1 -mr-1 space-y-1.5">
            {(telemetry || []).map((t, i) => {
              const meta = ENGINES.find((e) => e.key === t.engine);
              const dotColor = meta?.dot ?? 'bg-slate-500';
              return (
                <motion.div
                  key={`${t.ts}-${i}`}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: Math.min(i * 0.03, 0.3) }}
                  className="flex items-start gap-2.5 px-3 py-2 rounded-xl bg-theme-panel border border-theme hover:bg-white/5 transition-colors"
                >
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0 mt-1.5 ${dotColor}`} />
                  <span className="text-[9px] font-mono text-theme-secondary/50 shrink-0 mt-0.5 tabular-nums">
                    {fmtClock(t.ts)}
                  </span>
                  <span className="text-[11px] font-semibold text-theme-primary leading-snug break-words min-w-0">
                    {t.message}
                  </span>
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="shrink-0 pt-3 border-t border-theme">
        <p className="text-[10px] text-theme-secondary font-semibold">
          Pushed every 10s via snapshot poll — SSE retired to stop 24/7 billed executions
        </p>
      </div>
    </motion.div>
  );
};
