import React, { useState } from 'react';
import { X } from 'lucide-react';
import type { PromoCampaign } from '../../lib/campaigns';
import { snoozeCampaign, promoEvent } from '../../lib/campaigns';

const ACCENTS: Record<string, string> = {
  purple: 'border-purple-500/30 bg-purple-500/10',
  emerald: 'border-emerald-500/30 bg-emerald-500/10',
  amber: 'border-amber-500/30 bg-amber-500/10',
  sky: 'border-sky-500/30 bg-sky-500/10',
};

const CTA: Record<string, string> = {
  purple: 'bg-purple-600 hover:bg-purple-500',
  emerald: 'bg-emerald-600 hover:bg-emerald-500',
  amber: 'bg-amber-600 hover:bg-amber-500',
  sky: 'bg-sky-600 hover:bg-sky-500',
};

export const PromoCard: React.FC<{
  campaign: PromoCampaign;
  onAction: (c: PromoCampaign) => void;
  onSnoozed?: (id: string) => void;
  compact?: boolean;
}> = ({ campaign, onAction, onSnoozed, compact = false }) => {
  const [gone, setGone] = useState(false);
  if (gone) return null;
  const dismiss = () => {
    snoozeCampaign(campaign.id);
    promoEvent('promo_dismiss', campaign.id);
    setGone(true);
    onSnoozed?.(campaign.id);
  };
  return (
    <div className={`relative rounded-2xl border ${ACCENTS[campaign.accent]} p-5 sm:p-6 overflow-hidden`}>
      <button
        onClick={dismiss}
        aria-label={`Dismiss ${campaign.title} for 7 days`}
        title="Hide for 7 days"
        className="absolute top-3 right-3 p-1.5 rounded-lg text-theme-secondary hover:text-theme-primary hover:bg-white/10 transition-all"
      >
        <X className="w-3.5 h-3.5" />
      </button>
      <p className="text-[10px] font-black uppercase tracking-widest text-theme-secondary">{campaign.eyebrow}</p>
      <h3 className={`font-black text-theme-primary ${compact ? 'text-base' : 'text-xl'} mt-1 pr-8`}>
        <span className="mr-2">{campaign.icon}</span>{campaign.title}
      </h3>
      <p className={`text-theme-secondary mt-2 leading-relaxed ${compact ? 'text-xs' : 'text-sm'}`}>{campaign.body}</p>
      <button
        onClick={() => { promoEvent('promo_cta', campaign.id); onAction(campaign); }}
        className={`mt-4 px-5 py-2 rounded-xl text-white text-xs font-bold uppercase tracking-widest transition-all ${CTA[campaign.accent]}`}
      >
        {campaign.ctaLabel}
      </button>
    </div>
  );
};
