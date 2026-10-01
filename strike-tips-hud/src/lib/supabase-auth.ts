import { createClient, type SupabaseClient, type Session } from '@supabase/supabase-js';

// Supabase Auth for Strike Tips (Oct-2026). Google OAuth only.
// Publishable key is safe in the browser; RLS enforces row isolation.
// Service-role key must NEVER appear here — backend (Modal) only.
const URL = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const KEY = import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY as string | undefined;

let client: SupabaseClient | null = null;

export function supaConfigured(): boolean {
  return Boolean(URL && KEY);
}

export function supa(): SupabaseClient | null {
  if (!supaConfigured()) return null;
  if (!client) client = createClient(URL as string, KEY as string);
  return client;
}

export async function signInWithGoogle(): Promise<void> {
  const c = supa();
  if (!c) throw new Error('Supabase not configured');
  const { error } = await c.auth.signInWithOAuth({
    provider: 'google',
    options: { redirectTo: window.location.origin },
  });
  if (error) throw error;
}

export async function signOut(): Promise<void> {
  const c = supa();
  if (c) await c.auth.signOut();
}

export async function currentSession(): Promise<Session | null> {
  const c = supa();
  if (!c) return null;
  const { data } = await c.auth.getSession();
  return data.session;
}

/** JWT for authenticated backend calls (added to Authorization header). */
export async function accessToken(): Promise<string | null> {
  const s = await currentSession();
  return s?.access_token ?? null;
}
