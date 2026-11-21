import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';

/**
 * "Prices are not live" indicator (Nov-2026).
 *
 * The odds monitor stamps `fetch_ok` / `stale` / `stale_since` on every
 * snapshot, but nothing in the HUD read them. During the Betway 403 waves the
 * card stayed on screen looking live while every price was hours old — the one
 * failure mode a punter cannot detect for themselves.
 *
 * Two tiers (Nov-21, after a weekend of 90%-failure waves made the full banner
 * fire every other cycle and read like a site-wide outage):
 *
 *  - SHORT outage (< 20 min): a quiet one-line chip. The monitor retries every
 *    5 minutes and usually recovers on the next cycle, so shouting is noise.
 *  - SUSTAINED outage (>= 20 min): the full amber banner, because prices on
 *    screen are now materially wrong and staying wrong.
 *
 * The age comes from the server's `stale_since` (which the backend now carries
 * across failed cycles), so it reports true outage length rather than "time
 * since this tab noticed". Neither tier is dismissable: hiding a stale price
 * warning is exactly the mistake this exists to prevent.
 */
const ESCALATE_AFTER_MS = 20 * 60 * 1000;

const formatAge = (ms: number): string => {
  const mins = Math.max(0, Math.floor(ms / 60000));
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
};

export const FeedStaleBanner: React.FC = () => {
  const { feedOk, feedStale, feedError, feedStaleSince, events } = useHUD();
  const down = feedOk === false || feedStale;

  // The store only re-renders when a poll lands; during a full API outage the
  // age would sit frozen. Tick while down so the chip/banner stay truthful.
  const [, tick] = React.useState(0);
  React.useEffect(() => {
    if (!down) return;
    const id = window.setInterval(() => tick((n) => n + 1), 30000);
    return () => window.clearInterval(id);
  }, [down]);

  if (!down) return null;

  const ageMs = feedStaleSince ? Math.max(0, Date.now() - feedStaleSince) : 0;
  const raceCount = Object.keys(events || {}).length;
  const reason = feedError
    ? feedError.replace(/^Max retries reached:\s*/i, '').slice(0, 80)
    : null;

  // Short outage: one muted line, no alarm colour, no error text.
  if (ageMs < ESCALATE_AFTER_MS) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="mb-3 inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[11px] text-white/55"
      >
        <RefreshCw className="h-3 w-3 shrink-0 opacity-70" aria-hidden="true" />
        <span>
          Refreshing prices
          {feedStaleSince ? ` · last update ${formatAge(ageMs)} ago` : ''}
        </span>
      </div>
    );
  }

  return (
    <div
      role="status"
      aria-live="polite"
      className="mb-4 flex items-start gap-3 rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm"
    >
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-400" aria-hidden="true" />
      <div className="min-w-0">
        <p className="font-bold text-amber-300">Odds feed is not live</p>
        <p className="mt-0.5 text-white/75">
          The odds monitor could not refresh prices for the last {formatAge(ageMs)}
          {raceCount > 0 ? ` — the ${raceCount} race${raceCount === 1 ? '' : 's'} below are the last card it fetched` : ''}
          . Treat every price as <strong className="text-white">out of date</strong> until this clears.
        </p>
        {reason && (
          <p className="mt-1 font-mono text-[11px] uppercase tracking-wide text-amber-200/60">
            {reason}
          </p>
        )}
      </div>
    </div>
  );
};
