import React, { useState } from 'react';
import { signInWithGoogle } from '../../lib/supabase-auth';

/** Slim banner over public views (support/legal) for logged-out visitors. */
export const GuestBanner: React.FC = () => {
  const [busy, setBusy] = useState(false);
  const go = async () => {
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch {
      setBusy(false);
    }
  };
  return (
    <div className="mb-4 flex flex-wrap items-center gap-3 rounded-xl border border-purple-500/30 bg-purple-500/10 px-4 py-3 text-sm">
      <span className="text-white/80">You're browsing as a guest — sign in for live racing, alerts and your bankroll.</span>
      <button
        onClick={go}
        disabled={busy}
        className="ml-auto rounded-lg bg-purple-600 hover:bg-purple-500 px-4 py-1.5 text-xs font-bold uppercase tracking-widest transition-all disabled:opacity-60"
      >
        {busy ? 'Redirecting…' : 'Sign In'}
      </button>
    </div>
  );
};
