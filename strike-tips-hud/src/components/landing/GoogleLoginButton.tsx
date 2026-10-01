import React, { useState } from 'react';
import { signInWithGoogle, supaConfigured } from '../../lib/supabase-auth';

export const GoogleLoginButton: React.FC<{ label?: string; className?: string }> = ({
  label = 'Google Login',
  className = '',
}) => {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const go = async () => {
    setError(null);
    if (!supaConfigured()) {
      setError('Login is not configured on this deployment yet.');
      return;
    }
    setBusy(true);
    try {
      await signInWithGoogle();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Login failed — try again.');
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col items-start gap-2">
      <button
        onClick={go}
        disabled={busy}
        className={`inline-flex items-center gap-3 px-6 py-3 rounded-xl bg-white/10 hover:bg-white/15 border border-white/10 font-semibold text-white transition-all disabled:opacity-60 ${className}`}
      >
        <svg width="22" height="22" viewBox="0 0 48 48" aria-hidden="true">
          <path fill="#FFC107" d="M43.6 20.1H42V20H24v8h11.3C33.7 32.7 29.2 36 24 36c-6.6 0-12-5.4-12-12s5.4-12 12-12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 13 4 4 13 4 24s9 20 20 20 20-9 20-20c0-1.3-.1-2.6-.4-3.9z" />
          <path fill="#FF3D00" d="M6.3 14.7l6.6 4.8C14.7 15.1 19 12 24 12c3.1 0 5.9 1.2 8 3l5.7-5.7C34.3 6.1 29.4 4 24 4 16.3 4 9.7 8.3 6.3 14.7z" />
          <path fill="#4CAF50" d="M24 44c5.2 0 9.9-2 13.4-5.2l-6.2-5.2C29.2 35.1 26.7 36 24 36c-5.2 0-9.6-3.3-11.3-8l-6.5 5C9.5 39.6 16.2 44 24 44z" />
          <path fill="#1976D2" d="M43.6 20.1H42V20H24v8h11.3c-.8 2.3-2.3 4.3-4.1 5.6l6.2 5.2C36.9 39.2 44 34 44 24c0-1.3-.1-2.6-.4-3.9z" />
        </svg>
        {busy ? 'Redirecting…' : label}
      </button>
      {error && <p className="text-xs text-red-400 max-w-xs">{error}</p>}
    </div>
  );
};
