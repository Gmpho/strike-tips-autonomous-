import React, { useState, useEffect, useMemo, useRef } from 'react';
import useSWR from 'swr';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Trophy, Award, Users, BookOpen, CalendarDays,
} from 'lucide-react';
import { apiFetch } from '../../lib/api-fetch';
import { useSupabaseSession } from '../../hooks/useSupabaseSession';
import { useIsLight } from '../../hooks/useIsLight';
import { Avatar, type AvatarDescriptor } from './Avatar';
import { PicksHistoryTable } from './PicksHistoryTable';
import { ApexChart } from '../analytics/ApexChart';
import { apexBaseFor, APEX_ACCENT } from '../analytics/apex-theme';

const DECAY_DAYS = 7;
const REGIONS = [
  { code: '', label: 'All regions' },
  { code: 'SA', label: 'South Africa' },
  { code: 'UK_IE', label: 'UK & Ireland' },
  { code: 'USA', label: 'USA' },
  { code: 'AUS', label: 'Australia' },
  { code: 'HK', label: 'Hong Kong' },
  { code: 'JP', label: 'Japan' },
  { code: 'CAN', label: 'Canada' },
  { code: 'FRA', label: 'France' },
  { code: 'OTHER', label: 'Other' },
];

const jsonFetcher = async (url: string) => {
  const r = await apiFetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

const MEDAL: Record<number, string> = { 1: '🥇', 2: '🥈', 3: '🥉' };

/** One ranked board row (today: cohorts; players appear once they settle). */
interface Row {
  rank: number;
  entity_type: string;
  entity_id: string;
  handle: string;
  avatar?: AvatarDescriptor | null;
  region: string;
  settled: number;
  pending?: number;
  wins: number;
  strike_rate: number;
  total_points: number;
  weekly_points: number;
  avg_points_per_tip: number;
  form_rating: number;
  value_index: number;
  qualified: boolean;
  /** Settled tips still needed to reach the ranked board (0 once qualified). */
  needs?: number;
  /** Playing, but under the qualification gate — shown as "provisional", not failing. */
  provisional?: boolean;
  decayed: boolean;
  last_settled: string | null;
}

/** The signed-in punter's own line, shown even before they qualify. */
interface MeSummary {
  user_id: string;
  handle: string;
  avatar: AvatarDescriptor;
  summary: {
    tips: number; settled: number; wins: number; points: number;
    qualified: boolean; needed: number;
  };
}

export const LeaderboardView: React.FC = () => {
  const [region, setRegion] = useState('');
  const [scope, setScope] = useState<'all' | 'region' | 'tier' | 'track'>('all');
  const [sort, setSort] = useState<'form' | 'value' | 'strike' | 'weekly' | 'total'>('form');
  const [tab, setTab] = useState<'record' | 'players' | 'meetings' | 'formula'>('record');
  const [expandedPlayer, setExpandedPlayer] = useState<string | null>(null);
  const [playerPicks, setPlayerPicks] = useState<Record<string, any[]>>({});
  const [loadingPicks, setLoadingPicks] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [expandedMeeting, setExpandedMeeting] = useState<string | null>(null);
  const [me, setMe] = useState<MeSummary | null>(null);

  const isLight = useIsLight();
  const tabsRef = useRef<HTMLDivElement>(null);

  // Switching tabs used to leave the new table below the hero, so Players
  // looked like it did nothing until you scrolled. Bring the tab bar to the
  // top of the scroll container instead.
  const selectTab = (t: typeof tab) => {
    setTab(t);
    requestAnimationFrame(() => {
      tabsRef.current?.scrollIntoView({ block: 'start' });
    });
  };

  const { session } = useSupabaseSession();
  const uid = session?.user?.id ?? null;
  const token = session?.access_token ?? null;

  useEffect(() => {
    // The board itself is public, but "your standing" is per-account. Clear
    // first so a switched account never sees the previous punter's line.
    setMe(null);
    if (!uid || !token) return;
    let cancelled = false;
    apiFetch('/api/league/me', {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
      .then(r => (r.ok ? r.json() : null))
      .then((d: MeSummary | null) => {
        if (!cancelled && d && d.user_id === uid) setMe(d);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [uid, token]);

  const url = `/api/league/board?scope=${scope}&sort=${sort}${region ? `&region=${region}` : ''}&limit=200`;
  const { data, isLoading, error } = useSWR(url, jsonFetcher, { refreshInterval: 60_000 });
  const { data: formula } = useSWR('/api/league/formula', jsonFetcher);
  // Today's cards are only needed on the Meetings tab — don't pay for them
  // on every leaderboard visit.
  const { data: racesData, isLoading: racesLoading } = useSWR(
    tab === 'meetings' ? '/api/league/races' : null,
    jsonFetcher,
    { refreshInterval: 120_000 },
  );

  const rows: Row[] = data?.rows || [];
  useEffect(() => {
    if (!expandedPlayer) return;
    if (playerPicks[expandedPlayer]) return;
    setLoadingPicks(expandedPlayer);
    apiFetch(`/api/league/tipster/${encodeURIComponent(expandedPlayer)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (d?.picks) setPlayerPicks(prev => ({ ...prev, [expandedPlayer]: d.picks }));
      })
      .catch(() => {})
      .finally(() => setLoadingPicks(null));
  }, [expandedPlayer]);
  // Every player row, including unranked ones (<5 settled tips). The ranked
  // board filters those out, but community tips should still be visible.
  const playerRows: Row[] = (data?.all_rows || []).filter((r: Row) => r.entity_type === 'player');
  // Ranked punters first, then whoever has settled the most, then points.
  // Unranked-but-active punters must never be buried under an empty board.
  const sortedPlayers = useMemo(() => [...playerRows].sort((a, b) => {
    if (a.qualified !== b.qualified) return a.qualified ? -1 : 1;
    if (b.settled !== a.settled) return b.settled - a.settled;
    if (b.total_points !== a.total_points) return b.total_points - a.total_points;
    return a.handle.localeCompare(b.handle);
  }), [data]);

  // One card per meeting, ordered by first race off time.
  const meetings = useMemo(() => {
    const list: any[] = racesData?.races || [];
    const map = new Map<string, { course: string; region: string; races: any[] }>();
    for (const r of list) {
      const key = r.course || 'Unknown';
      if (!map.has(key)) map.set(key, { course: key, region: r.region || '—', races: [] });
      map.get(key)!.races.push(r);
    }
    const out = [...map.values()];
    for (const m of out) {
      m.races.sort((a, b) => Number(a.race_number || 0) - Number(b.race_number || 0));
    }
    out.sort((a, b) => String(a.races[0]?.off || '').localeCompare(String(b.races[0]?.off || '')));
    return out;
  }, [racesData]);
  const ranked = rows; // already qualified+non-decayed from API
  const pageSize = 40;
  const totalPages = Math.max(1, Math.ceil(ranked.length / pageSize));
  const pageRows = ranked.slice((page - 1) * pageSize, page * pageSize);

  // highlight strip
  const topForm = [...ranked].sort((a, b) => b.form_rating - a.form_rating)[0];
  const bestValue = [...ranked].sort((a, b) => b.value_index - a.value_index)[0];
  const topStrike = [...ranked].filter(r => r.settled >= 10).sort((a, b) => b.strike_rate - a.strike_rate)[0];
  const weeklyLeader = [...ranked].sort((a, b) => b.weekly_points - a.weekly_points)[0];
  const rising = [...ranked].sort((a, b) => b.settled - a.settled)[0];

  const asOf = data?.as_of ? new Date(data.as_of) : null;
  const ageMin = asOf ? Math.round((Date.now() - asOf.getTime()) / 60000) : null;

  return (
    <div className="league-view flex-1 flex flex-col min-h-0 overflow-y-auto">
      <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8">
        {/* Hero */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-gradient-to-br from-yellow-400 to-amber-500 rounded-2xl shadow-lg shadow-yellow-500/20 mb-4">
            <Trophy className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-3xl md:text-4xl font-black tracking-tight text-white mb-2">Leaderboard</h1>
          <p className="text-base text-slate-300 max-w-xl mx-auto mb-4">
            Ranked by current form — average points per settled tip over the last 30 days, so the board always shows who's hot right now.
          </p>
          <div className="flex flex-wrap justify-center gap-2 mb-4">
            {['First choice wins', 'Exact 1-2-3', 'Full sweep'].map(t => (
              <span key={t} className="flex items-center gap-1.5 bg-white/10 backdrop-blur-sm px-3 py-1.5 rounded-full text-xs text-slate-200">
                <Award className="w-3.5 h-3.5 text-yellow-400" /> {t}
              </span>
            ))}
          </div>
          <div className="flex flex-wrap justify-center gap-2">
            <a href="/leaderboard/monthly" className="text-sm text-slate-400 hover:text-white px-4 py-2 rounded-full bg-white/5">November Race</a>
            <button className="text-sm text-slate-400 hover:text-white px-4 py-2 rounded-full bg-white/5 inline-flex items-center gap-2">
              <Users className="w-4 h-4" /> View Regional Leaderboards
            </button>
          </div>
        </div>

        {/* Your standing — avatar + handle, even while unranked */}
        {me && (
          <div className="mb-6 flex flex-wrap items-center gap-4 bg-slate-800/60 border border-slate-700 rounded-xl p-4">
            <Avatar avatar={me.avatar} name={me.handle} size={48} />
            <div className="min-w-0">
              <div className="text-white font-bold truncate flex items-center gap-2">
                {me.handle}
                <span className="text-[10px] uppercase tracking-wider text-yellow-400 bg-yellow-500/15 px-1.5 py-0.5 rounded">You</span>
              </div>
              <div className="text-xs text-slate-400 mt-0.5">
                {me.summary.tips} tips · {me.summary.settled} settled · {me.summary.wins} wins · {me.summary.points} pts
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">
                {me.summary.qualified
                  ? 'Qualified for the ranked board.'
                  : `Unranked — ${me.summary.needed} more settled tip${me.summary.needed === 1 ? '' : 's'} to qualify.`}
              </div>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <div className="w-20 h-20">
                <ApexChart
                  type="radialBar"
                  series={[Math.round((me.summary.wins / Math.max(1, me.summary.settled)) * 100)]}
                  options={{
                    ...apexBaseFor(isLight),
                    labels: ['Strike'],
                    colors: [APEX_ACCENT],
                    chart: { sparkline: { enabled: true } },
                    plotOptions: {
                      radialBar: {
                        hollow: { size: '55%' },
                        dataLabels: {
                          name: { show: false },
                          value: { fontSize: '14px', fontWeight: 900, color: isLight ? '#0f172a' : '#fff', formatter: (v: number) => `${v}%` },
                        },
                      },
                    },
                  }}
                  height={80}
                />
              </div>
              <div className="flex flex-col gap-1 text-xs">
                <a href="/profile" className="font-semibold text-yellow-400 hover:underline">
                  My profile →
                </a>
                <a href="/picks" className="text-slate-400 hover:text-white">
                  Change avatar
                </a>
              </div>
            </div>
          </div>
        )}

        {/* Highlight strip — cohort stats, so Record only. */}
        {tab === 'record' && ranked.length > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
            {[
              { label: 'Top Form', row: topForm, val: (r: Row | undefined) => r?.form_rating.toFixed(1), sub: 'form rating' },
              { label: 'Best Value', row: bestValue, val: (r: Row | undefined) => r?.value_index.toFixed(0), sub: 'value index' },
              { label: 'Top Strike Rate', row: topStrike, val: (r: Row | undefined) => r ? `${(r.strike_rate * 100).toFixed(0)}%` : '—', sub: '30-day strike rate' },
              { label: 'Weekly Leader', row: weeklyLeader, val: (r: Row | undefined) => r?.weekly_points.toLocaleString(), sub: 'points this week' },
              { label: 'Rising Star', row: rising, val: () => 'New', sub: 'settled tips' },
            ].map(c => (
              <div key={c.label} className="bg-slate-800/60 border border-slate-700 rounded-xl p-3 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">{c.label}</div>
                <div className="text-white font-bold text-sm truncate">{c.row?.handle || '—'}</div>
                <div className="text-yellow-400 font-black text-lg">{c.val(c.row)}</div>
                <div className="text-[10px] text-slate-500">{c.sub}</div>
              </div>
            ))}
          </div>
        )}

        {/* Tabs */}
        <div ref={tabsRef} className="flex gap-2 mb-4 border-b border-slate-700 scroll-mt-2">
          {(['record', 'players', 'meetings', 'formula'] as const).map(t => (
            <button key={t} onClick={() => selectTab(t)}
              className={`px-4 py-2 text-sm font-semibold capitalize border-b-2 transition-colors ${tab === t ? 'border-yellow-400 text-white' : 'border-transparent text-slate-400 hover:text-white'}`}>
              {t === 'record' ? 'Record' : t === 'players' ? 'Players' : t === 'meetings' ? 'Meetings' : 'How scoring works'}
            </button>
          ))}
        </div>

        {tab === 'formula' && formula && (
          <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-5 mb-6">
            <h2 className="text-white font-bold mb-3 flex items-center gap-2"><BookOpen className="w-4 h-4" /> Published formula</h2>
            <ul className="space-y-1 text-sm text-slate-300 mb-4">
              {formula.rules.map((r: string, i: number) => <li key={i} className="flex gap-2"><span className="text-yellow-400">•</span>{r}</li>)}
            </ul>
            <div className="grid md:grid-cols-3 gap-3">
              {formula.worked_examples.map((e: any, i: number) => (
                <div key={i} className="bg-slate-900/60 rounded-lg p-3 text-xs">
                  <div className="text-slate-400 mb-1">{e.scenario}</div>
                  <div className="text-white font-bold">= {e.points} points</div>
                  {e.base_points != null && <div className="text-slate-500">base {e.base_points} + SP bonus {e.sp_bonus}</div>}
                </div>
              ))}
            </div>
            <p className="text-xs text-slate-500 mt-3">
              Form: {formula.form_scale}. Value: {formula.value_scale}. Min {formula.min_tips_to_qualify} settled tips to qualify; {formula.decay_days}-day inactivity decay.
            </p>
          </div>
        )}

        {tab === 'record' && (
          <>
            {/* Controls */}
            <div className="flex flex-wrap items-center gap-3 mb-4">
              <select value={region} onChange={e => { setRegion(e.target.value); setPage(1); }}
                className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2">
                {REGIONS.map(r => <option key={r.code} value={r.code}>{r.label}</option>)}
              </select>
              <select value={scope} onChange={e => { setScope(e.target.value as any); setPage(1); }}
                className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2">
                <option value="all">All cohorts</option>
                <option value="region">Regions only</option>
                <option value="tier">Tiers only</option>
                <option value="track">Tracks only</option>
              </select>
              <div className="ml-auto flex items-center gap-1 text-xs text-slate-400">
                Sort:
                {(['form', 'value', 'strike', 'weekly', 'total'] as const).map(s => (
                  <button key={s} onClick={() => { setSort(s); setPage(1); }}
                    className={`px-2 py-1 rounded ${sort === s ? 'bg-yellow-500/20 text-yellow-400' : 'hover:text-white'}`}>
                    {s}
                  </button>
                ))}
              </div>
            </div>

            {isLoading && (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
              </div>
            )}
            {error && <div className="text-center text-red-400 py-8">Failed to load board.</div>}

            {!isLoading && ranked.length === 0 && (
              <div className="text-center py-12 text-slate-400">
                <Trophy className="w-10 h-10 mx-auto mb-3 opacity-40" />
                <p className="mb-1">No qualified rows yet.</p>
                <p className="text-xs">Needs {data?.min_tips ?? 5} settled tips in 30 days. Sample: {data?.total_rows ?? 0} rows.</p>
              </div>
            )}

            {ranked.length > 0 && (
              <>
                <div className="overflow-x-auto rounded-xl border border-slate-700">
                  <table className="min-w-full text-sm">
                    <thead className="bg-gradient-to-r from-slate-800 to-slate-900">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300">Rank</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300">Cohort</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300">Form</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300 hidden md:table-cell">Value</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300 hidden md:table-cell">Strike</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300 hidden md:table-cell">Weekly</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300 hidden md:table-cell">Total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {pageRows.map(r => (
                        <React.Fragment key={r.entity_id + r.region}>
                          <tr className="border-t border-slate-700/60 hover:bg-slate-800/40 cursor-pointer"
                              onClick={() => setExpanded(expanded === r.entity_id ? null : r.entity_id)}>
                            <td className="px-4 py-3 font-bold text-white">
                              {MEDAL[r.rank] || r.rank}
                            </td>
                            <td className="px-4 py-3">
                              <div className="flex items-center gap-2.5">
                                <Avatar avatar={r.avatar} name={r.handle} size={30} />
                                <div className="min-w-0">
                                  <div className="text-white font-semibold truncate">{r.handle}</div>
                                  <div className="text-[10px] text-slate-500">{r.region} · {r.settled} settled</div>
                                </div>
                              </div>
                            </td>
                            <td className="px-4 py-3 text-yellow-400 font-bold">{r.form_rating.toFixed(1)}</td>
                            <td className="px-4 py-3 text-slate-300 hidden md:table-cell">{r.value_index.toFixed(0)}</td>
                            <td className="px-4 py-3 text-slate-300 hidden md:table-cell">{(r.strike_rate * 100).toFixed(0)}%</td>
                            <td className="px-4 py-3 text-slate-300 hidden md:table-cell">{r.weekly_points.toLocaleString()}</td>
                            <td className="px-4 py-3 text-slate-300 hidden md:table-cell">{r.total_points.toLocaleString()}</td>
                          </tr>
                          <AnimatePresence>
                            {expanded === r.entity_id && (
                              <tr className="bg-slate-900/40">
                                <td colSpan={7} className="px-4 py-4">
                                  <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                                    className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
                                    <div><div className="text-slate-500">Settled</div><div className="text-white font-bold">{r.settled}</div></div>
                                    <div><div className="text-slate-500">Wins</div><div className="text-white font-bold">{r.wins}</div></div>
                                    <div><div className="text-slate-500">Avg pts/tip</div><div className="text-white font-bold">{r.avg_points_per_tip.toFixed(2)}</div></div>
                                    <div><div className="text-slate-500">Last settled</div><div className="text-white font-bold">{r.last_settled ? r.last_settled.slice(0, 10) : '—'}</div></div>
                                  </motion.div>
                                </td>
                              </tr>
                            )}
                          </AnimatePresence>
                        </React.Fragment>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Pagination */}
                <div className="flex items-center justify-between mt-4 text-xs text-slate-400">
                  <span>Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, ranked.length)} of {ranked.length} results</span>
                  <div className="flex gap-1">
                    <button disabled={page <= 1} onClick={() => setPage(p => Math.max(1, p - 1))}
                      className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40">Prev</button>
                    <button disabled={page >= totalPages} onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                      className="px-3 py-1 rounded bg-slate-800 disabled:opacity-40">Next</button>
                  </div>
                </div>
              </>
            )}

            {/* Freshness */}
            <div className="mt-6 text-xs text-slate-500 text-center">
              {data?.total_rows ?? 0} cohort-rows from {data?.ranked_rows ?? 0} ranked · min {data?.min_tips ?? 5} settled tips · {DECAY_DAYS}-day decay
              {ageMin != null && ` · scores updated ${ageMin}m ago`}
              {ageMin != null && ageMin > 60 * 48 && ' · stale'}
            </div>
          </>
        )}

        {tab === 'players' && (
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
              <h3 className="text-white font-bold text-sm flex items-center gap-2">
                <Users className="w-4 h-4 text-slate-400" /> Players
                <span className="text-xs text-slate-500 font-normal">({sortedPlayers.length})</span>
              </h3>
              <p className="text-[11px] text-slate-500">
                {data?.min_tips ?? 5} settled tips to rank · tap a row for picks
              </p>
            </div>

            {sortedPlayers.length === 0 ? (
              <div className="text-center py-10 text-slate-400 bg-slate-800/40 border border-slate-700 rounded-xl">
                <Users className="w-9 h-9 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No player picks yet.</p>
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-700">
                <table className="min-w-full text-sm">
                  <thead className="bg-gradient-to-r from-slate-800 to-slate-900">
                    <tr>
                      <th className="px-3 md:px-4 py-3 text-left text-xs font-semibold uppercase text-slate-300">Player</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300">Settled</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300 hidden sm:table-cell">Pending</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300 hidden md:table-cell">Wins</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300">Strike</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300">Points</th>
                      <th className="px-2 md:px-4 py-3 text-right text-xs font-semibold uppercase text-slate-300">Form</th>
                      <th className="px-1 md:px-2 py-3" />
                    </tr>
                  </thead>
                  <tbody>
                    {sortedPlayers.map(r => {
                      const open = expandedPlayer === r.entity_id;
                      const picks = playerPicks[r.entity_id] || [];
                      const needs = r.needs ?? Math.max(0, (data?.min_tips ?? 5) - r.settled);
                      return (
                        <React.Fragment key={r.entity_id}>
                          <tr
                            className="border-t border-slate-700/60 hover:bg-slate-800/40 cursor-pointer"
                            onClick={() => setExpandedPlayer(open ? null : r.entity_id)}>
                            <td className="px-3 md:px-4 py-3">
                              <div className="flex items-center gap-2.5">
                                <Avatar avatar={r.avatar} name={r.handle} size={30} />
                                <div className="min-w-0">
                                  <div className="text-white font-semibold truncate">{r.handle}</div>
                                  {r.qualified ? (
                                    <span className="text-[10px] text-emerald-400">ranked</span>
                                  ) : r.provisional ? (
                                    <span className="text-[10px] text-amber-400">provisional · {needs} to rank</span>
                                  ) : (
                                    <span className="text-[10px] text-slate-500">{needs} to rank</span>
                                  )}
                                </div>
                              </div>
                            </td>
                            <td className="px-2 md:px-4 py-3 text-right text-slate-300">{r.settled}</td>
                            <td className="px-2 md:px-4 py-3 text-right text-slate-300 hidden sm:table-cell">{r.pending || 0}</td>
                            <td className="px-2 md:px-4 py-3 text-right text-slate-300 hidden md:table-cell">{r.wins}</td>
                            <td className="px-2 md:px-4 py-3 text-right text-slate-300">
                              {r.settled > 0 ? `${Math.round(r.strike_rate * 100)}%` : '—'}
                            </td>
                            <td className="px-2 md:px-4 py-3 text-right text-slate-200 font-semibold">{r.total_points}</td>
                            <td className="px-2 md:px-4 py-3 text-right text-yellow-400 font-bold">
                              {r.settled > 0 ? r.form_rating.toFixed(1) : '—'}
                            </td>
                            <td className="px-1 md:px-2 py-3 text-slate-500 text-xs text-center">{open ? '▲' : '▼'}</td>
                          </tr>
                          {open && (
                            <tr className="bg-theme-secondary/20 border-t border-theme">
                              <td colSpan={8} className="p-2 sm:p-4">
                                {loadingPicks === r.entity_id && picks.length === 0 ? (
                                  <div className="flex items-center justify-center py-6">
                                    <div className="w-5 h-5 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
                                  </div>
                                ) : picks.length === 0 ? (
                                  <p className="text-theme-secondary/60 text-xs py-3 text-center">No picks on record.</p>
                                ) : (
                                  <PicksHistoryTable
                                    picks={picks}
                                    title={`${r.handle}'s Picks`}
                                    compact={true}
                                    pageSize={8}
                                  />
                                )}
                              </td>
                            </tr>
                          )}
                        </React.Fragment>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {tab === 'meetings' && (
          <div>
            <div className="flex flex-wrap items-baseline justify-between gap-2 mb-3">
              <h3 className="text-white font-bold text-sm flex items-center gap-2">
                <CalendarDays className="w-4 h-4 text-slate-400" /> Meetings
                <span className="text-xs text-slate-500 font-normal">({meetings.length})</span>
              </h3>
              <p className="text-[11px] text-slate-500">Today's cards · tap a meeting for its races</p>
            </div>

            {racesLoading && (
              <div className="flex items-center justify-center py-12">
                <div className="w-8 h-8 border-2 border-purple-500/20 border-t-purple-500 rounded-full animate-spin" />
              </div>
            )}

            {!racesLoading && meetings.length === 0 && (
              <div className="text-center py-10 text-slate-400 bg-slate-800/40 border border-slate-700 rounded-xl">
                <CalendarDays className="w-9 h-9 mx-auto mb-2 opacity-40" />
                <p className="text-sm">No race cards loaded yet.</p>
                <p className="text-xs mt-1">Meetings appear once the odds monitor publishes a snapshot.</p>
              </div>
            )}

            <div className="space-y-2">
              {meetings.map(m => {
                const open = expandedMeeting === m.course;
                const first = m.races[0];
                const last = m.races[m.races.length - 1];
                return (
                  <div key={m.course} className="bg-slate-800/40 border border-slate-700 rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpandedMeeting(open ? null : m.course)}
                      className="w-full flex items-center gap-3 p-3 text-left hover:bg-slate-700/30">
                      <div className="w-9 h-9 rounded-lg bg-yellow-500/15 flex items-center justify-center shrink-0">
                        <CalendarDays className="w-4 h-4 text-yellow-400" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="text-white font-semibold truncate">{m.course}</div>
                        <div className="text-[11px] text-slate-400">
                          {m.region} · {m.races.length} race{m.races.length === 1 ? '' : 's'}
                          {first?.off && ` · ${first.off}–${last?.off}`}
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-yellow-400 font-black text-sm">{m.races.length}</div>
                        <div className="text-[10px] text-slate-500">races</div>
                      </div>
                      <span className="text-slate-500 text-xs">{open ? '▲' : '▼'}</span>
                    </button>
                    {open && (
                      <div className="border-t border-slate-700/60 p-3 space-y-1.5">
                        {m.races.map(r => (
                          <div key={r.race_id} className="flex items-center gap-2 text-xs">
                            <span className="text-slate-500 w-12 shrink-0">R{r.race_number}</span>
                            <span className="text-slate-300 flex-1 min-w-0 truncate">
                              {r.off || '—'}
                              {r.distance_m ? ` · ${r.distance_m}m` : ''}
                              {r.field_size ? ` · ${r.field_size} runners` : ''}
                            </span>
                            <a href="/picks" className="text-yellow-400 hover:underline shrink-0">Pick →</a>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};