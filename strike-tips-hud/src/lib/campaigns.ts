/** PromoHub campaign engine (Oct-2026): convert curious signups to core.
 *  Local TS config now; Supabase `campaigns` table later with zero component changes.
 *  Rules: targeting ALL-must-pass, 7-day snooze, max 1 popup/session, never over betting flows.
 */

export type PromoAction =
  | { kind: 'install-pwa' }
  | { kind: 'goto-settings-telegram' }
  | { kind: 'goto-exotics' }
  | { kind: 'goto-support' }
  | { kind: 'join-whatsapp' }
  | { kind: 'dismiss' };

export interface PromoTargeting {
  /** require Google session: true = logged in only, false = logged out only, undefined = any */
  session?: boolean;
  /** require telegram link state: 'linked' | 'unlinked', undefined = any */
  telegram?: 'linked' | 'unlinked';
  /** require PWA state: 'installable' (can install, hasn't) | 'installed' | 'browser' */
  pwa?: 'installable' | 'installed' | 'browser';
  /** show only on these app views (dashboard slot renders anywhere, card filters) */
  views?: string[];
  /** show only if user never completed this key (e.g. viewed exotics pools) */
  unseenKey?: string;
}

export interface PromoCampaign {
  id: string;
  eyebrow: string;
  title: string;
  body: string;
  icon: string; // emoji anchor
  accent: 'purple' | 'emerald' | 'amber' | 'sky';
  ctaLabel: string;
  action: PromoAction;
  targeting: PromoTargeting;
  priority: number; // lower = first
}

export const CAMPAIGNS: PromoCampaign[] = [
  {
    id: 'telegram-connect',
    eyebrow: 'Race-day alerts',
    title: 'Get every flag on Telegram',
    body: 'Value alerts, settlement pings and scan reports — pushed to your phone while the card is live.',
    icon: '✈️',
    accent: 'sky',
    ctaLabel: 'Connect Telegram',
    action: { kind: 'goto-settings-telegram' },
    targeting: { session: true, telegram: 'unlinked' },
    priority: 1,
  },
  {
    id: 'pwa-install',
    eyebrow: 'Home-screen app',
    title: 'Install Strike Tips',
    body: 'One tap, offline racecards, faster loads. No app store, no account needed beyond Google.',
    icon: '📲',
    accent: 'emerald',
    ctaLabel: 'Install App',
    action: { kind: 'install-pwa' },
    targeting: { pwa: 'installable' },
    priority: 2,
  },
  {
    id: 'exotics-intro',
    eyebrow: 'New here?',
    title: 'Exotics in plain words',
    body: 'Banker = your anchor horse. Savers = backup horses that keep the ticket alive. Pick the pool, we build the permutation.',
    icon: '🎰',
    accent: 'amber',
    ctaLabel: 'View pools',
    action: { kind: 'goto-exotics' },
    targeting: { unseenKey: 'pools-viewed' },
    priority: 3,
  },
  {
    id: 'whatsapp-community',
    eyebrow: 'Punters talk here',
    title: 'Join the WhatsApp group',
    body: 'Race-day chatter, extra eyes on the card, and your questions answered by real humans between scans.',
    icon: '💬',
    accent: 'emerald',
    ctaLabel: 'Join Group',
    action: { kind: 'join-whatsapp' },
    targeting: {},
    priority: 4,
  },
];

const SNOOZE_KEY = 'strike_promo_snooze';
const SEEN_KEY = 'strike_promo_seen';
const SNOOZE_MS = 7 * 24 * 3600 * 1000;

/** Official community group — invite link is public, safe to ship in client. */
export const WHATSAPP_GROUP_URL = 'https://chat.whatsapp.com/C6T9FuBiExK5jeNLooc7bW';

function readMap(key: string): Record<string, number> {
  try {
    return JSON.parse(localStorage.getItem(key) || '{}');
  } catch {
    return {};
  }
}

export function snoozeCampaign(id: string): void {
  try {
    const m = readMap(SNOOZE_KEY);
    m[id] = Date.now();
    localStorage.setItem(SNOOZE_KEY, JSON.stringify(m));
  } catch { /* private mode */ }
}

export function markSeen(key: string): void {
  try {
    const m = readMap(SEEN_KEY);
    m[key] = Date.now();
    localStorage.setItem(SEEN_KEY, JSON.stringify(m));
  } catch { /* private mode */ }
}

export function isSnoozed(id: string): boolean {
  const at = readMap(SNOOZE_KEY)[id];
  return typeof at === 'number' && Date.now() - at < SNOOZE_MS;
}

export interface PromoContext {
  loggedIn: boolean;
  telegramLinked: boolean | null; // null = unknown (don't filter on it)
  pwa: 'installable' | 'installed' | 'browser';
  view: string;
}

export function eligibleCampaigns(ctx: PromoContext): PromoCampaign[] {
  return CAMPAIGNS.filter((c) => {
    const t = c.targeting;
    if (isSnoozed(c.id)) return false;
    if (t.session === true && !ctx.loggedIn) return false;
    if (t.session === false && ctx.loggedIn) return false;
    if (t.telegram === 'linked' && ctx.telegramLinked !== true) return false;
    if (t.telegram === 'unlinked' && ctx.telegramLinked === true) return false;
    if (t.pwa && t.pwa !== ctx.pwa) return false;
    if (t.views && !t.views.includes(ctx.view)) return false;
    if (t.unseenKey) {
      const seen = readMap(SEEN_KEY)[t.unseenKey];
      if (seen) return false;
    }
    return true;
  }).sort((a, b) => a.priority - b.priority);
}

/** Funnel telemetry: impression / CTA / dismiss per campaign. */
export function promoEvent(kind: 'promo_impression' | 'promo_cta' | 'promo_dismiss', id: string, extra?: string): void {
  try {
    window.dispatchEvent(new CustomEvent('promo-telemetry', { detail: { kind, id, extra } }));
  } catch { /* noop */ }
  if (typeof console !== 'undefined') console.debug(`[promo] ${kind} ${id}${extra ? ` ${extra}` : ''}`);
}
