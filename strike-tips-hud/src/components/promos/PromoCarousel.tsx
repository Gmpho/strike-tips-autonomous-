import React, { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { PromoCampaign } from '../../lib/campaigns';
import { promoEvent } from '../../lib/campaigns';
import { PromoCard } from './PromoCard';

/** Dashboard carousel: swipeable promo rail above the race grid. Max 3,
 *  dots, auto-advance pauses on touch. Theme tokens only (dark/light safe). */
export const PromoCarousel: React.FC<{
  campaigns: PromoCampaign[];
  onAction: (c: PromoCampaign) => void;
}> = ({ campaigns, onAction }) => {
  const [idx, setIdx] = useState(0);
  const [paused, setPaused] = useState(false);
  const shown = campaigns.slice(0, 3);
  useEffect(() => {
    if (shown.length) promoEvent('promo_impression', shown[Math.min(idx, shown.length - 1)].id);
  }, []);
  useEffect(() => {
    if (paused || shown.length < 2) return;
    const t = setInterval(() => setIdx((i) => (i + 1) % shown.length), 8000);
    return () => clearInterval(t);
  }, [paused, shown.length]);
  if (!shown.length) return null;
  const cur = shown[idx % shown.length];
  return (
    <div
      className="w-full"
      onTouchStart={() => setPaused(true)}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <PromoCard key={cur.id} campaign={cur} onAction={onAction} />
      {shown.length > 1 && (
        <div className="flex items-center justify-center gap-2 mt-2">
          <button onClick={() => setIdx((idx - 1 + shown.length) % shown.length)} aria-label="Previous promotion"
            className="p-1 rounded-lg text-theme-secondary hover:text-theme-primary transition-all">
            <ChevronLeft className="w-4 h-4" />
          </button>
          {shown.map((c, i) => (
            <button key={c.id} onClick={() => setIdx(i)} aria-label={`Show promotion ${i + 1}`}
              className={`h-1.5 rounded-full transition-all ${i === idx % shown.length ? 'w-6 bg-purple-500' : 'w-1.5 bg-white/20'}`} />
          ))}
          <button onClick={() => setIdx((idx + 1) % shown.length)} aria-label="Next promotion"
            className="p-1 rounded-lg text-theme-secondary hover:text-theme-primary transition-all">
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      )}
    </div>
  );
};
