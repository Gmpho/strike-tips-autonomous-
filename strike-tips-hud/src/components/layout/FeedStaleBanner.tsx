import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { useHUD } from '../../hooks/useHUD';

/**
 * "Prices are not live" banner (Nov-2026).
 *
 * The odds monitor stamps `fetch_ok` and `stale` on every snapshot, but
 * nothing in the HUD read them. During the Betway 403 waves the card stayed
 * on screen looking live while every price was hours old — the one failure
 * mode a punter cannot detect for themselves.
 *
 * Kept deliberately non-dismissable: hiding it is exactly the mistake this
 * exists to prevent. Renders nothing while the feed is healthy.
 */
export const FeedStaleBanner: React.FC = () => {
  const { feedOk, feedStale, feedError, feedStaleSince, events } = useHUD();
  const down = feedOk === false || feedStale;
  if (!down) return null;

  const raceCount = Object.keys(events || {}).length;
  const ageMin = feedStaleSince
    ? Math.max(0, Math.floor((Date.now() - feedStaleSince) / 60000))
    : null;
  const ageText =
    ageMin === null
      ? null
      : ageMin < 60
        ? `${ageMin} min`
        : `${Math.floor(ageMin / 60)}h ${ageMin % 60}m`;
  const reason = feedError
    ? feedError.replace(/^Max retries reached:\s*/i, '').slice(0, 80)
    : null;

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
          The odds monitor could not refresh prices
          {ageText ? ` for the last ${ageText}` : ''}
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
