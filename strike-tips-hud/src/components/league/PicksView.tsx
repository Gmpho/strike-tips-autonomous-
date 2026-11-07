import React, { useState, useEffect, useMemo } from 'react';
import useSWR from 'swr';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Target, Clock, Lock, CheckCircle2, Users, ChevronDown, ChevronUp,
  Zap, History, Camera, X, ImageOff,
} from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';
import { useSupabaseSession } from '../../hooks/useSupabaseSession';
import { apiFetch } from '../../lib/api-fetch';
import { Avatar, PRESET_STYLES, type AvatarDescriptor } from './Avatar';

const jsonFetcher = async (url: string) => {
  const r = await apiFetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
};

interface Runner {
  number: string | number;
  name: string;
  odds: string | number;
  jockey?: string | null;
  trainer?: string | null;
  pedigree?: string | null;
  age?: string | number | null;
  weight?: string | null;
  draw?: number | null;
  form?: string | null;
  days_since_run?: number | null;
  rating?: number | null;
  claim?: string | null;
  star?: number | null;
}
interface Backer {
  handle: string | null;
  user_id: string | null;
  avatar: AvatarDescriptor | null;
  runner_number: number;
  runner_name: string | null;
}
interface Race {
  race_id: string;
  course: string;
  region: string;
  race_number: string | number;
  off: string;
  off_iso: string | null;
  field_size: number;
  runners: Runner[];
  is_finished: boolean;
  crowd: Record<string, number>;
  backers?: Backer[];
}

interface AvatarPreset { id: string; emoji: string; gradient?: string }

/** A pick as stored by the backend — history rows carry the race they were on. */
interface MePick {
  race_id: string;
  course?: string;
  race_number?: string | number;
  runner_number: number;
  runner_name?: string;
  pick_odds?: number;
  date?: string;
  off_iso?: string | null;
  settled?: boolean;
  won?: boolean;
  points?: number;
  created_at?: string;
}

interface Me {
  user_id: string;
  handle: string;
  avatar: AvatarDescriptor;
  has_google_avatar: boolean;
  google_avatar_url?: string | null;
  avatar_presets: AvatarPreset[];
  picks: MePick[];
  summary: {
    tips: number; settled: number; pending: number; wins: number; places: number;
    strike_rate: number; place_rate: number; points: number;
    qualified: boolean; needed: number;
  };
}

function lockAt(offIso: string | null): Date | null {
  if (!offIso) return null;
  const d = new Date(offIso);
  if (isNaN(d.getTime())) return null;
  return new Date(d.getTime() - 5 * 60 * 1000);
}

function countdown(ms: number): string {
  if (ms <= 0) return 'Locked';
  const s = Math.floor(ms / 1000);
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${m}:${sec.toString().padStart(2, '0')}`;
}

export const PicksView: React.FC = () => {
  const hud = useHUD();
  const { session } = useSupabaseSession();
  const [region, setRegion] = useState('SA');
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});
  const [submitting, setSubmitting] = useState<string | null>(null);
  const [now, setNow] = useState(Date.now());
  const [me, setMe] = useState<Me | null>(null);
  const [meVersion, setMeVersion] = useState(0);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  // The signed-in account. Everything below is keyed to this id, so switching
  // Google accounts can never show the previous punter's picks.
  const uid = session?.user?.id ?? null;
  const token = session?.access_token ?? null;

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    // Identity changed or signed out: drop the previous account's data BEFORE
    // any fetch, otherwise its picks stay on screen while the new one loads.
    setMe(null);
    setPickerOpen(false);
    if (!uid || !token) return;

    let cancelled = false;
    apiFetch('/api/league/me', {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
      .then(r => (r.ok ? r.json() : null))
      .then((d: Me | null) => {
        if (cancelled || !d) return;
        // Belt and braces: the backend scopes by token, but if the payload
        // ever describes a different user we refuse to render it.
        if (d.user_id !== uid) return;
        setMe(d);
      })
      .catch(() => {});

    return () => { cancelled = true; };
  }, [uid, token, meVersion]);

  // races from backend (for crowd + off_iso)
  const { data: racesData } = useSWR(`/api/league/races?region=${region}`, jsonFetcher, { refreshInterval: 30_000 });
  const apiRaces: Race[] = racesData?.races || [];

  // my picks derived from /me only — never merged from another source
  const myPicks = useMemo(() => {
    const m: Record<string, number> = {};
    for (const p of me?.picks || []) m[p.race_id] = p.runner_number;
    return m;
  }, [me]);

  // group hud events by course for today's races
  const events = Array.isArray(hud.events) ? hud.events : [];
  const todayRaces = useMemo(() => {
    const out: Race[] = [];
    for (const e of events) {
      const match = apiRaces.find(r => r.race_id === String(e.id));
      if (!match) continue;
      if (region && match.region !== region) continue;
      out.push(match);
    }
    if (out.length === 0 && apiRaces.length > 0) {
      return apiRaces.filter(r => !region || r.region === region);
    }
    return out.length > 0 ? out : apiRaces.filter(r => !region || r.region === region);
  }, [events, apiRaces, region]);

  const byCourse = useMemo(() => {
    const g: Record<string, Race[]> = {};
    for (const r of todayRaces) {
      (g[r.course] = g[r.course] || []).push(r);
    }
    return g;
  }, [todayRaces]);

  // Full pick history grouped by race day lives on /profile now — /picks is
  // today's card only, so it doesn't fetch or render yesterday's rows twice.

  const submitPick = async (race: Race, runner: Runner) => {
    if (!token) return;
    const key = `${race.race_id}-${runner.number}`;
    setSubmitting(key);
    try {
      const r = await apiFetch('/api/league/picks', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({
          race_id: race.race_id,
          course: race.course,
          race_number: race.race_number,
          off_iso: race.off_iso,
          runner_number: Number(runner.number),
          runner_name: runner.name,
          odds: Number(runner.odds) || 0,
          region: race.region,
          field_size: race.field_size,
        }),
      });
      if (r.ok) {
        setMeVersion(v => v + 1);
      } else {
        const err = await r.json().catch(() => ({}));
        const msg = Array.isArray(err.detail)
          ? err.detail.map((e: any) => e.msg || JSON.stringify(e)).join('; ')
          : (typeof err.detail === 'string' ? err.detail : JSON.stringify(err));
        alert(msg || 'Pick failed');
      }
    } finally {
      setSubmitting(null);
    }
  };

  const saveAvatar = async (mode: 'google' | 'preset' | 'initials', preset?: string) => {
    if (!token) return;
    setSavingAvatar(true);
    setAvatarError(null);
    try {
      const r = await apiFetch('/api/league/me/avatar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ mode, preset: preset ?? null }),
      });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) {
        setAvatarError(typeof d.detail === 'string' ? d.detail : 'Could not save that avatar');
        return;
      }
      setMe(prev => (prev ? { ...prev, avatar: d.avatar, has_google_avatar: d.has_google_avatar } : prev));
      setPickerOpen(false);
    } finally {
      setSavingAvatar(false);
    }
  };

  if (!session?.access_token) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center">
        <div>
          <Target className="w-12 h-12 text-purple-400 mx-auto mb-4 opacity-60" />
          <h2 className="text-xl font-bold text-white mb-2">Sign in to pick</h2>
          <p className="text-slate-400 text-sm max-w-sm mx-auto">
            Picks are tied to your account. Sign in with Google to submit one pick per race and climb the leaderboard.
          </p>
        </div>
      </div>
    );
  }

  const handle = me?.handle || session.user?.user_metadata?.full_name || session.user?.email || 'You';
  const todayCount = Object.keys(byCourse).length > 0
    ? Object.keys(myPicks).filter(rid => todayRaces.some(r => r.race_id === rid)).length
    : Object.keys(myPicks).length;
  const summary = me?.summary;
  const activeMode = me?.avatar?.mode || 'initials';

  return (
    <div className="league-view flex-1 flex flex-col min-h-0 overflow-y-auto">
      <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl md:text-3xl font-black text-white flex items-center gap-2">
              <Target className="w-7 h-7 text-yellow-400" /> Your Picks
            </h1>
            <p className="text-sm text-slate-400 mt-1">One pick per race. Locks 5 minutes before the off.</p>
          </div>

          {/* Signed in as — avatar + handle, with the avatar picker entry point */}
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-2 bg-slate-800/60 border border-slate-700 rounded-full pl-1.5 pr-3 py-1.5">
              <Avatar avatar={me?.avatar} name={handle} size={32} />
              <div className="leading-tight">
                <div className="text-white text-sm font-semibold max-w-[10rem] truncate">{handle}</div>
                <button
                  onClick={() => setPickerOpen(v => !v)}
                  className="text-[11px] text-yellow-400 hover:underline flex items-center gap-1">
                  <Camera className="w-3 h-3" /> Change avatar
                </button>
              </div>
            </div>
            <select value={region} onChange={e => setRegion(e.target.value)}
              className="bg-slate-800 border border-slate-700 text-white text-sm rounded-lg px-3 py-2">
              <option value="">All regions</option>
              <option value="SA">South Africa</option>
              <option value="UK_IE">UK & Ireland</option>
              <option value="USA">USA</option>
              <option value="AUS">Australia</option>
              <option value="HK">Hong Kong</option>
              <option value="JP">Japan</option>
            </select>
          </div>
        </div>

        {/* Avatar picker */}
        <AnimatePresence>
          {pickerOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="overflow-hidden mb-6">
              <div className="bg-slate-800/60 border border-slate-700 rounded-xl p-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h3 className="text-white font-bold text-sm">How you appear on the leaderboard</h3>
                    <p className="text-xs text-slate-400 mt-0.5">
                      The board is public. Keep your Google photo, or switch to an avatar for privacy.
                    </p>
                  </div>
                  <button onClick={() => setPickerOpen(false)} className="text-slate-400 hover:text-white p-1">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex flex-wrap gap-3">
                  {/* Google photo (only if the account actually has one) */}
                  <button
                    onClick={() => saveAvatar('google')}
                    disabled={savingAvatar || !me?.has_google_avatar}
                    title={me?.has_google_avatar ? 'Use my Google photo' : 'No Google photo on this account'}
                    className={`relative flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors ${
                      activeMode === 'google' ? 'border-yellow-400 bg-yellow-500/10' : 'border-slate-700 hover:bg-slate-700/40'
                    } ${!me?.has_google_avatar ? 'opacity-40 cursor-not-allowed' : ''}`}>
                    <Avatar
                      avatar={{ mode: 'google', url: me?.google_avatar_url || null }}
                      name={handle}
                      size={44}
                      className={me?.has_google_avatar ? '' : 'opacity-60'}
                    />
                    <span className="text-[10px] text-slate-300">Google</span>
                    {!me?.has_google_avatar && <ImageOff className="absolute top-1 right-1 w-3 h-3 text-slate-500" />}
                  </button>

                  {Object.entries(PRESET_STYLES).map(([id, preset]) => (
                    <button
                      key={id}
                      onClick={() => saveAvatar('preset', id)}
                      disabled={savingAvatar}
                      title={preset.label}
                      className={`flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors ${
                        activeMode === 'preset' && me?.avatar?.preset === id
                          ? 'border-yellow-400 bg-yellow-500/10'
                          : 'border-slate-700 hover:bg-slate-700/40'
                      }`}>
                      <Avatar avatar={{ mode: 'preset', preset: id }} name={handle} size={44} />
                      <span className="text-[10px] text-slate-300">{preset.label}</span>
                    </button>
                  ))}

                  {/* Plain initials */}
                  <button
                    onClick={() => saveAvatar('initials')}
                    disabled={savingAvatar}
                    title="Just my initials"
                    className={`flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors ${
                      activeMode === 'initials' ? 'border-yellow-400 bg-yellow-500/10' : 'border-slate-700 hover:bg-slate-700/40'
                    }`}>
                    <Avatar avatar={{ mode: 'initials' }} name={handle} size={44} />
                    <span className="text-[10px] text-slate-300">Initials</span>
                  </button>
                </div>

                {avatarError && <p className="text-xs text-red-400 mt-3">{avatarError}</p>}
                {savingAvatar && <p className="text-xs text-slate-400 mt-3">Saving…</p>}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        {/* Season summary for this account */}
        {summary && summary.tips > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3 mb-6">
            {[
              { label: 'Tips', value: summary.tips },
              { label: 'Settled', value: summary.settled },
              { label: 'Wins', value: summary.wins },
              { label: 'Placed', value: summary.places },
              { label: 'Strike', value: `${Math.round(summary.strike_rate * 100)}%` },
              { label: 'Points', value: summary.points },
            ].map(s => (
              <div key={s.label} className="bg-slate-800/60 border border-slate-700 rounded-xl p-3 text-center">
                <div className="text-[10px] uppercase tracking-wider text-slate-400 mb-1">{s.label}</div>
                <div className="text-white font-black text-lg">{s.value}</div>
              </div>
            ))}
          </div>
        )}

        <div className="flex items-center justify-between mb-3 flex-wrap gap-2">
          <h2 className="text-lg font-bold text-white flex items-center gap-2">
            <Zap className="w-4 h-4 text-yellow-400" /> Today's races
          </h2>
          <div className="text-sm text-slate-400">
            Your picks today: <span className="text-yellow-400 font-bold">{todayCount}</span>
          </div>
        </div>

        {Object.keys(byCourse).length === 0 && (
          <div className="text-center py-12 text-slate-400">
            <Target className="w-10 h-10 mx-auto mb-3 opacity-40" />
            <p>No races found for this region today.</p>
          </div>
        )}

        {Object.entries(byCourse).map(([course, races]) => (
          <div key={course} className="mb-6">
            <h3 className="text-base font-bold text-white mb-3 flex items-center gap-2">
              <Zap className="w-4 h-4 text-yellow-400" /> {course}
              <span className="text-xs text-slate-500 font-normal">({races.length} races)</span>
            </h3>
            <div className="space-y-3">
              {races.sort((a, b) => Number(a.race_number) - Number(b.race_number)).map(race => {
                const lock = lockAt(race.off_iso);
                const locked = lock ? now >= lock.getTime() : false;
                const myPick = myPicks[race.race_id];
                const isExpanded = expanded[race.race_id] !== false;
                const crowd = race.crowd || {};
                const totalPicks = Object.values(crowd).reduce((a, b) => a + b, 0);
                // "Others" only: my own row has no business in a crowd strip.
                const others = (race.backers || []).filter(b => b.user_id !== uid);

                return (
                  <div key={race.race_id} className="bg-slate-800/60 border border-slate-700 rounded-xl overflow-hidden">
                    <button
                      onClick={() => setExpanded(prev => ({ ...prev, [race.race_id]: !isExpanded }))}
                      className="w-full flex items-center justify-between px-4 py-3 hover:bg-slate-700/40 transition-colors">
                      <div className="flex items-center gap-3">
                        <span className="text-white font-bold">R{race.race_number}</span>
                        <span className="text-slate-400 text-sm">{race.off} SAST</span>
                        <span className="text-slate-500 text-xs">{race.field_size} runners</span>
                        {myPick && (
                          <span className="flex items-center gap-1 text-xs bg-yellow-500/20 text-yellow-400 px-2 py-0.5 rounded-full">
                            <CheckCircle2 className="w-3 h-3" /> You: #{myPick}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        {locked ? (
                          <span className="flex items-center gap-1 text-xs text-red-400"><Lock className="w-3.5 h-3.5" /> Locked</span>
                        ) : lock ? (
                          <span className="flex items-center gap-1 text-xs text-amber-400"><Clock className="w-3.5 h-3.5" /> {countdown(lock.getTime() - now)}</span>
                        ) : null}
                        {isExpanded ? <ChevronUp className="w-4 h-4 text-slate-400" /> : <ChevronDown className="w-4 h-4 text-slate-400" />}
                      </div>
                    </button>

                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          className="overflow-hidden">
                          <div className="px-4 pb-4">
                            {totalPicks > 0 && (
                              <div className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                                <Users className="w-3 h-3" /> {totalPicks} pick{totalPicks !== 1 ? 's' : ''} submitted
                              </div>
                            )}
                            <div className="space-y-1">
                              {race.runners.map(runner => {
                                const rn = Number(runner.number);
                                const isMyPick = myPick === rn;
                                const backers = crowd[String(runner.number)] || crowd[runner.number] || 0;
                                const maxBackers = Math.max(...Object.values(crowd), 1);
                                const barPct = totalPicks > 0 ? (backers / maxBackers) * 100 : 0;

                                return (
                                  <div key={runner.number}
                                    className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors ${isMyPick ? 'bg-yellow-500/10 border border-yellow-500/30' : 'hover:bg-slate-700/40'}`}>
                                    <span className="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center text-xs font-bold text-white flex-shrink-0">
                                      {runner.number}
                                    </span>
                                    <div className="flex-1 min-w-0">
                                      {/* Horse name is the headline (TipMeerkat pattern) */}
                                      <div className="flex items-baseline gap-2 min-w-0">
                                        <span className="text-white text-sm font-semibold truncate">{runner.name}</span>
                                        {runner.star && runner.star > 0 && (
                                          <span className="text-[10px] text-yellow-400 shrink-0">★{runner.star}</span>
                                        )}
                                      </div>
                                      {/* Jockey / trainer wraps instead of being cut off —
                                          on a phone the old single truncated line hid
                                          half the connections. */}
                                      <div className="text-[10px] text-slate-400 mt-0.5 leading-snug break-words">
                                        {runner.jockey || '—'} · {runner.trainer || '—'}
                                      </div>
                                      {(runner.age || runner.weight || runner.draw) && (
                                        <div className="flex flex-wrap items-center gap-1 mt-1">
                                          {runner.age && (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 whitespace-nowrap">{runner.age}</span>
                                          )}
                                          {runner.weight && (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 whitespace-nowrap">{runner.weight}</span>
                                          )}
                                          {runner.draw ? (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 whitespace-nowrap">Draw {runner.draw}</span>
                                          ) : null}
                                        </div>
                                      )}
                                      {(runner.form || runner.rating || runner.days_since_run != null) && (
                                        <div className="flex flex-wrap items-center gap-1 mt-1">
                                          {runner.form && (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono whitespace-nowrap">Form {runner.form}</span>
                                          )}
                                          {runner.days_since_run != null && (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono whitespace-nowrap">{runner.days_since_run}d</span>
                                          )}
                                          {runner.rating ? (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono whitespace-nowrap">R{runner.rating}</span>
                                          ) : null}
                                          {runner.claim && runner.claim !== '0' ? (
                                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-700/40 text-slate-300 font-mono whitespace-nowrap">-{runner.claim}</span>
                                          ) : null}
                                        </div>
                                      )}
                                      {runner.pedigree && (
                                        <div className="text-[10px] text-slate-500 mt-1 italic leading-snug break-words">
                                          {runner.pedigree}
                                        </div>
                                      )}
                                      {backers > 0 && (
                                        <div className="flex items-center gap-2 mt-1">
                                          <div className="flex-1 h-1 bg-slate-700 rounded-full overflow-hidden">
                                            <div className="h-full bg-yellow-500/60 rounded-full" style={{ width: `${barPct}%` }} />
                                          </div>
                                          <span className="text-[10px] text-slate-500">{backers}</span>
                                        </div>
                                      )}
                                    </div>
                                    <span className="text-slate-400 text-sm w-12 text-right shrink-0">{runner.odds}</span>
                                    {!locked && !race.is_finished && (
                                      <button
                                        onClick={() => submitPick(race, runner)}
                                        disabled={submitting === `${race.race_id}-${runner.number}` || isMyPick}
                                        className={`px-3 py-1.5 rounded-lg text-xs font-bold transition-colors flex-shrink-0 ${
                                          isMyPick
                                            ? 'bg-yellow-500/20 text-yellow-400 cursor-default'
                                            : 'bg-purple-600 hover:bg-purple-500 text-white disabled:opacity-50'
                                        }`}>
                                        {isMyPick ? 'Your pick' : submitting === `${race.race_id}-${runner.number}` ? '...' : 'Pick'}
                                      </button>
                                    )}
                                    {locked && !isMyPick && (
                                      <span className="text-xs text-slate-600 flex-shrink-0">locked</span>
                                    )}
                                  </div>
                                );
                              })}
                            </div>

                            {/* Public crowd strip — clearly labelled, and never
                                mixed into "your picks" above. */}
                            {others.length > 0 && (
                              <div className="mt-3 pt-3 border-t border-slate-700/60">
                                <div className="text-[11px] uppercase tracking-wider text-slate-500 mb-2 flex items-center gap-1">
                                  <Users className="w-3 h-3" /> What others picked
                                </div>
                                <div className="flex flex-wrap gap-2">
                                  {others.map((b, i) => (
                                    <div key={`${b.user_id || b.handle || 'x'}-${b.runner_number}-${i}`}
                                      className="flex items-center gap-2 bg-slate-900/60 border border-slate-700/60 rounded-full pl-1 pr-3 py-1">
                                      <Avatar avatar={b.avatar} name={b.handle} size={22} />
                                      <span className="text-[11px] text-slate-300 max-w-[8rem] truncate">{b.handle || 'Punter'}</span>
                                      <span className="text-[11px] font-bold text-yellow-400">
                                        #{b.runner_number} {b.runner_name || ''}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                );
              })}
            </div>
          </div>
        ))}

        {/* Season summary — the full, day-grouped history lives on /profile
            so this page stays about today's racing. */}
        <div className="mt-8 bg-slate-800/40 border border-slate-700 rounded-xl p-4">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
            <div className="flex items-center gap-2">
              <History className="w-4 h-4 text-yellow-400" />
              <h2 className="text-sm font-bold text-white">Your season</h2>
            </div>
            {summary ? (
              <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-400">
                <span><b className="text-white">{summary.tips}</b> tip{summary.tips === 1 ? '' : 's'}</span>
                <span><b className="text-white">{summary.settled}</b> settled</span>
                {summary.pending > 0 && <span><b className="text-amber-400">{summary.pending}</b> pending</span>}
                <span><b className="text-white">{summary.wins}</b> wins</span>
                <span><b className="text-white">{summary.places}</b> placed</span>
                <span><b className="text-yellow-400">{summary.points}</b> pts</span>
                <span><b className="text-white">{Math.round(summary.strike_rate * 100)}%</b> strike</span>
              </div>
            ) : (
              <span className="text-xs text-slate-500">Loading your record…</span>
            )}
            <a href="/profile" className="ml-auto text-xs font-semibold text-yellow-400 hover:underline whitespace-nowrap">
              View full history →
            </a>
          </div>

          {summary && summary.tips === 0 && (
            <p className="text-xs text-slate-500 mt-2">
              No picks yet. Choose a runner above to open your account.
            </p>
          )}
          {summary && !summary.qualified && summary.tips > 0 && (
            <p className="text-xs text-slate-500 mt-2">
              {summary.needed} more settled tip{summary.needed === 1 ? '' : 's'} to qualify for the leaderboard.
            </p>
          )}
        </div>
      </div>
    </div>
  );
};
