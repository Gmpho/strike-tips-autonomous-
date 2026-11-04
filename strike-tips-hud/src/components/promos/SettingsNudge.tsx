import React, { useState } from 'react';
import { CAMPAIGNS } from '../../lib/campaigns';
import { PromoCard } from './PromoCard';

/** Persistent (non-popup) nudge above the Telegram link card.
 *  Shows only while unlinked; disappears once linked. No snooze — it lives
 *  where the action happens. */
export const SettingsNudge: React.FC = () => {
  const [linked] = useState<boolean>(() => {
    try {
      return localStorage.getItem('strike_telegram_linked') === '1';
    } catch {
      return true; // unknown: don't nag
    }
  });
  if (linked) return null;
  const campaign = CAMPAIGNS.find((c) => c.id === 'telegram-connect');
  if (!campaign) return null;
  return (
    <div className="mb-1">
      <PromoCard
        campaign={campaign}
        compact
        onAction={() => {
          document.getElementById('telegram-link-card')?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }}
      />
    </div>
  );
};
