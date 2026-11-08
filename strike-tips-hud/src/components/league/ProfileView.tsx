import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Camera, X, ImageOff, Target, Trophy,
} from 'lucide-react';
import { useSupabaseSession } from '../../hooks/useSupabaseSession';
import { useIsLight } from '../../hooks/useIsLight';
import { apiFetch } from '../../lib/api-fetch';
import { Avatar, PRESET_STYLES, type AvatarDescriptor } from './Avatar';
import { PicksHistoryTable } from './PicksHistoryTable';
import { ApexChart } from '../analytics/ApexChart';
import { apexBaseFor, APEX_UP, APEX_DOWN, APEX_ACCENT } from '../analytics/apex-theme';

interface AvatarPreset { id: string; emoji: string; gradient?: string }
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
  finish_position?: number | null;
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

export const ProfileView: React.FC = () => {
  const { session } = useSupabaseSession();
  const isLight = useIsLight();
  const [me, setMe] = useState<Me | null>(null);
  const [pickerOpen, setPickerOpen] = useState(false);
  const [savingAvatar, setSavingAvatar] = useState(false);
  const [avatarError, setAvatarError] = useState<string | null>(null);

  const uid = session?.user?.id ?? null;
  const token = session?.access_token ?? null;

  useEffect(() => {
    if (!uid || !token) return;
    let cancelled = false;
    apiFetch('/api/league/me', {
      headers: { Authorization: `Bearer ${token}` },
      cache: 'no-store',
    })
      .then(r => (r.ok ? r.json() : null))
      .then((d: Me | null) => {
        if (cancelled || !d || d.user_id !== uid) return;
        setMe(d);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [uid, token]);

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
          <h2 className="text-xl font-bold text-white mb-2">Sign in to view your profile</h2>
          <p className="text-slate-400 text-sm max-w-sm mx-auto">
            Your profile, avatar and pick history are tied to your Google account.
          </p>
        </div>
      </div>
    );
  }

  const handle = me?.handle || session.user?.user_metadata?.full_name || session.user?.email || 'You';
  const summary = me?.summary;
  const activeMode = me?.avatar?.mode || 'initials';

  return (
    <div className="league-view flex-1 flex flex-col min-h-0 overflow-y-auto">
      <div className="px-4 md:px-8 lg:px-12 py-4 md:py-8">
        <div className="flex items-start justify-between mb-6 flex-wrap gap-4">
          <div>
            <h1 className="text-2xl font-bold text-white flex items-center gap-2">
              <Trophy className="w-5 h-5 text-purple-400" /> My profile
            </h1>
            <p className="text-slate-400 text-sm mt-1">
              How you appear on the public leaderboard. Your Google photo is never changed — only this avatar is.
            </p>
          </div>
        </div>

        {/* Avatar + handle */}
        <div className="flex items-center gap-4 mb-6">
          <Avatar avatar={me?.avatar} name={handle} size={72} />
          <div>
            <div className="text-white text-xl font-bold">{handle}</div>
            <button
              onClick={() => setPickerOpen(v => !v)}
              className="text-[12px] text-yellow-400 hover:underline flex items-center gap-1 mt-1">
              <Camera className="w-3.5 h-3.5" /> Change avatar
            </button>
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
                  <button
                    onClick={() => saveAvatar('google')}
                    disabled={savingAvatar || !me?.has_google_avatar}
                    title={me?.has_google_avatar ? 'Use my Google photo' : 'No Google photo on this account'}
                    className={`relative flex flex-col items-center gap-1 p-2 rounded-xl border transition-colors ${
                      activeMode === 'google' ? 'border-yellow-400 bg-yellow-500/10' : 'border-slate-700 hover:bg-slate-700/40'
                    } ${!me?.has_google_avatar ? 'opacity-40 cursor-not-allowed' : ''}`}>
                    <Avatar avatar={{ mode: 'google', url: me?.google_avatar_url || null }} name={handle} size={44} />
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

        {/* Stats */}
        {summary && (
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

        {/* Stats charts (ApexCharts) */}
        {summary && summary.tips > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
              <h3 className="text-white font-bold text-sm mb-2">Outcome mix</h3>
              <ApexChart
                type="donut"
                series={[summary.wins, Math.max(0, summary.places - summary.wins), Math.max(0, summary.settled - summary.places), summary.pending]}
                options={{
                  ...apexBaseFor(isLight),
                  labels: ['Wins', 'Placed 2-4', 'Unplaced', 'Pending'],
                  colors: [APEX_UP, '#38bdf8', APEX_DOWN, '#f59e0b'],
                  legend: { position: 'bottom', labels: { colors: isLight ? '#475569' : '#94a3b8' } },
                  plotOptions: { pie: { donut: { size: '62%' } } },
                  dataLabels: { enabled: true, style: { colors: ['#fff'] } },
                }}
                height={240}
              />
            </div>
            <div className="bg-slate-800/40 border border-slate-700 rounded-xl p-4">
              <h3 className="text-white font-bold text-sm mb-2">Strike rate</h3>
              <ApexChart
                type="radialBar"
                series={[Math.round(summary.strike_rate * 100)]}
                options={{
                  ...apexBaseFor(isLight),
                  labels: ['Strike'],
                  colors: [APEX_ACCENT],
                  plotOptions: {
                    radialBar: {
                      hollow: { size: '60%' },
                      dataLabels: {
                        name: { show: true, color: isLight ? '#475569' : '#94a3b8' },
                        value: { fontSize: '28px', fontWeight: 900, color: isLight ? '#0f172a' : '#fff', formatter: (v: number) => `${v}%` },
                      },
                    },
                  },
                }}
                height={240}
              />
            </div>
          </div>
        )}

        {/* Pick history */}
        <PicksHistoryTable
          picks={me?.picks || []}
          title="Your Pick History"
          pageSize={10}
        />
      </div>
    </div>
  );
};