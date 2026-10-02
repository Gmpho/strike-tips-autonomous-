import React, { useCallback, useEffect, useState } from 'react';
import { Copy, RefreshCw, Send, Unlink, Zap } from 'lucide-react';
import { apiFetch } from '../../lib/api-fetch';
import { accessToken, supaConfigured, currentSession } from '../../lib/supabase-auth';

type LinkState =
  | { phase: 'loading' }
  | { phase: 'signin' }
  | { phase: 'unlinked'; code: string | null }
  | { phase: 'linked'; username: string | null };

/** Authed fetch with the user's Supabase JWT + Turnstile retry (same as /api/config saves). */
async function authed(path: string, init?: RequestInit): Promise<Response> {
  const token = await accessToken();
  const doIt = () =>
    apiFetch(path, {
      ...init,
      headers: { ...(init?.headers || {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    });
  let res = await doIt();
  if (res.status === 401) {
    const { ensureSession } = await import('../../lib/session-client');
    const outcome = await ensureSession();
    if (outcome === 'ok') res = await doIt();
  }
  return res;
}

/** Telegram Alerts passcode card (CryptoPulse-style): NOT LINKED shows the
 *  ST- code + copy/open-bot; CONNECTED shows the @username + test/unlink. */
export const TelegramLinkCard: React.FC = () => {
  const [state, setState] = useState<LinkState>({ phase: 'loading' });
  const [botName, setBotName] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const refreshStatus = useCallback(async () => {
    if (!supaConfigured()) { setState({ phase: 'signin' }); return; }
    const s = await currentSession();
    if (!s) { setState({ phase: 'signin' }); return; }
    try {
      const res = await authed('/api/telegram/link-status');
      if (res.status === 401 || res.status === 503) throw new Error(`HTTP ${res.status}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setState(body.linked
        ? { phase: 'linked', username: body.username }
        : { phase: 'unlinked', code: null });
    } catch {
      // Signed in but backend unreachable/misconfigured — say so plainly
      // instead of offering a passcode that can't work.
      setMsg('Signed in, but the link service is unreachable. Try again in a minute.');
      setState({ phase: 'unlinked', code: null });
    }
  }, []);

  useEffect(() => {
    refreshStatus();
    apiFetch('/api/telegram/bot-name').then(async (r) => {
      if (r.ok) {
        const b = await r.json().catch(() => null);
        if (b?.username) setBotName(b.username);
      }
    }).catch(() => {});
  }, [refreshStatus]);

  const mint = async () => {
    setBusy(true); setMsg(null);
    try {
      const res = await authed('/api/telegram/link-code', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const body = await res.json();
      setState({ phase: 'unlinked', code: body.code });
    } catch {
      setMsg('Could not mint a code — backend unreachable or signed out.');
    } finally {
      setBusy(false);
    }
  };

  const copyStart = async (code: string) => {
    try {
      await navigator.clipboard.writeText(`/start ${code}`);
      setMsg('Copied — paste it to the bot in Telegram.');
    } catch {
      setMsg(`Copy this: /start ${code}`);
    }
  };

  const test = async () => {
    setBusy(true); setMsg(null);
    try {
      const res = await authed('/api/telegram/test', { method: 'POST' });
      setMsg(res.ok ? 'Test sent — check your Telegram.' : 'Test failed — is the chat still open?');
    } catch {
      setMsg('Test failed — backend unreachable.');
    } finally {
      setBusy(false);
    }
  };

  const unlink = async () => {
    if (!window.confirm('Unlink Telegram? Alerts stop immediately.')) return;
    setBusy(true);
    try {
      await authed('/api/telegram/unlink', { method: 'POST' });
      setState({ phase: 'unlinked', code: null });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-4 rounded-2xl border border-theme bg-theme-secondary/30 p-5">
      <div className="flex items-center gap-2 mb-1">
        <Send className="w-4 h-4 text-sky-400" />
        <span className="text-sm font-black text-theme-primary uppercase tracking-widest">Telegram Alerts</span>
        {state.phase === 'linked' && (
          <span className="ml-auto text-[10px] font-black px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">CONNECTED</span>
        )}
        {(state.phase === 'unlinked' || state.phase === 'signin') && (
          <span className="ml-auto text-[10px] font-black px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">NOT LINKED</span>
        )}
      </div>
      <p className="text-xs text-theme-secondary mb-4">Instant value alerts and profit reports on your phone.</p>

      {state.phase === 'loading' && <p className="text-xs text-theme-secondary animate-pulse">Checking link status…</p>}

      {state.phase === 'signin' && (
        <p className="text-xs text-theme-secondary">Sign in with Google first — the passcode binds Telegram to your account.</p>
      )}

      {state.phase === 'unlinked' && (
        <>
          {!state.code ? (
            <button onClick={mint} disabled={busy}
              className="px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-60">
              {busy ? 'Working…' : 'Generate Passcode'}
            </button>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 rounded-xl bg-black/30 border border-theme px-4 py-3">
                <div>
                  <p className="text-[10px] uppercase tracking-widest text-theme-secondary">Your Passcode</p>
                  <p className="text-xl font-black tracking-widest text-purple-400">{state.code}</p>
                </div>
                <button onClick={mint} disabled={busy} title="Refresh code"
                  className="text-xs text-theme-secondary hover:text-theme-primary underline underline-offset-2">
                  Refresh Code
                </button>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={() => copyStart(state.code as string)}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-purple-500/40 text-purple-300 text-xs font-bold uppercase tracking-widest hover:bg-purple-500/10 transition-all">
                  <Copy className="w-3.5 h-3.5" /> Copy /start Command
                </button>
                {botName && (
                  <a href={`https://t.me/${botName}?start=${state.code}`}
                    target="_blank" rel="noreferrer"
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-purple-600 hover:bg-purple-500 text-white text-xs font-bold uppercase tracking-widest transition-all">
                    <Send className="w-3.5 h-3.5" /> Open @{botName} in Telegram
                  </a>
                )}
              </div>
              <p className="mt-2 text-[11px] text-theme-secondary">Send <b>/start {state.code}</b> to the bot — single-use, expires in 15 minutes.</p>
            </>
          )}
        </>
      )}

      {state.phase === 'linked' && (
        <>
          <div className="rounded-xl bg-emerald-500/10 border border-emerald-500/30 px-4 py-3 flex items-center gap-2">
            <span className="text-xs text-theme-secondary">Linked Account:</span>
            <span className="text-sm font-black text-emerald-400">{state.username ? `@${state.username}` : 'Connected'}</span>
            <span className="ml-auto text-emerald-400">✓</span>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button onClick={test} disabled={busy}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl border border-sky-500/40 text-sky-300 text-xs font-bold uppercase tracking-widest hover:bg-sky-500/10 transition-all disabled:opacity-60">
              <Zap className="w-3.5 h-3.5" /> Test Connection
            </button>
            <button onClick={unlink} disabled={busy}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-theme-secondary text-xs font-bold uppercase tracking-widest hover:text-red-400 transition-all disabled:opacity-60">
              <Unlink className="w-3.5 h-3.5" /> Unlink
            </button>
          </div>
        </>
      )}

      {msg && <p className="mt-3 text-xs text-theme-secondary">{msg}</p>}
      {state.phase === 'linked' && (
        <button onClick={refreshStatus} className="mt-2 inline-flex items-center gap-1 text-[11px] text-theme-secondary hover:text-theme-primary">
          <RefreshCw className="w-3 h-3" /> Refresh status
        </button>
      )}
    </div>
  );
};
