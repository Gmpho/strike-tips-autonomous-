import { useEffect, useState } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supa, supaConfigured, currentSession } from '../lib/supabase-auth';

export interface SupaSession {
  configured: boolean;
  loading: boolean;
  session: Session | null;
}

/** Tracks the Supabase Google session. Unconfigured (no VITE_ keys) -> configured:false. */
export function useSupabaseSession(): SupaSession {
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const configured = supaConfigured();

  useEffect(() => {
    if (!configured) {
      setLoading(false);
      return;
    }
    let mounted = true;
    currentSession()
      .then((s) => { if (mounted) { setSession(s); setLoading(false); } })
      .catch(() => { if (mounted) setLoading(false); });
    const c = supa();
    const { data } = c!.auth.onAuthStateChange((_event, s) => {
      if (mounted) setSession(s);
    });
    return () => { mounted = false; data.subscription.unsubscribe(); };
  }, [configured]);

  return { configured, loading, session };
}
