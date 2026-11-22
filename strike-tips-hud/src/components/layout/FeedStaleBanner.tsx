import React from 'react';
import { RefreshCw } from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';

/**
 * Quiet price-age chip (Nov-2026, simplified Nov-22).
 *
 * Originally this had two tiers: a chip under 20 minutes and a full amber
 * "Odds feed is not live" banner above it. The banner fired on every Betway
 * 403 wave and read like a site-wide outage, so it is gone — the user asked
 * for the noise, not the information. What stays is the truth that is hard
 * to infer yourself: how old the prices on screen are.
 *
 * Anything over 15 minutes is called out as out of date; newer than that is
 * just "refreshing", because the monitor retries every few minutes. The age
 * comes from the server's `stale_since`, which the backend carries across
 * failed cycles, so it measures the real outage rather than when this tab
 * noticed. Not dismissable.
 */
const QUIET_CUTOFF_MS = 15 * 60 * 1000;

const formatAge = (ms: number): string => {
  const mins = Math.max(0, Math.floor(ms / 60000));
  if (mins < 60) return `${mins}m`;
  return `${Math.floor(mins / 60)}h ${mins % 60}m`;
};

export const FeedStaleBanner: React.FC = () => {
  const { feedOk, feedStale, feedStaleSince } = useHUD();
  const down = feedOk === false || feedStale;

  // The store only re-renders when a poll lands; during a full API outage the
  // age would sit frozen. Tick while down so the chip stays truthful.
  const [, tick] = React.useState(0);
  React.useEffect(() => {
    if (!down) return;
    const id = window.setInterval(() => tick((n) => n + 1), 30000);
    return () => window.clearInterval(id);
  }, [down]);

  if (!down) return null;

  const ageMs = feedStaleSince ? Math.max(0, Date.now() - feedStaleSince) : 0;
  const outdated = ageMs > QUIET_CUTOFF_MS;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`mb-3 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] ${
        outdated
          ? 'border-white/15 bg-white/5 text-white/60'
          : 'border-white/10 bg-white/5 text-white/45'
      }`}
    >
      <RefreshCw className="h-3 w-3 shrink-0 opacity-70" aria-hidden="true" />
      <span>
        {outdated ? 'Prices out of date' : 'Refreshing prices'}
        {feedStaleSince ? ` · last update ${formatAge(ageMs)} ago` : ''}
      </span>
    </div>
  );
};
