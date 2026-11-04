import { useCallback } from 'react';
import type { PromoCampaign } from '../lib/campaigns';
import { markSeen, WHATSAPP_GROUP_URL } from '../lib/campaigns';
import { usePWA } from './usePWA';

/** Maps campaign CTAs to real app actions. */
export function usePromoActions(navigate: (view: string) => void) {
  const { installPWA } = usePWA();
  return useCallback(
    (c: PromoCampaign) => {
      switch (c.action.kind) {
        case 'install-pwa':
          installPWA();
          break;
        case 'goto-settings-telegram':
          navigate('settings');
          break;
        case 'goto-exotics':
          markSeen('pools-viewed');
          navigate('exotics');
          break;
        case 'goto-support':
          navigate('support');
          break;
        case 'join-whatsapp':
          window.open(WHATSAPP_GROUP_URL, '_blank', 'noopener');
          break;
        case 'dismiss':
          break;
      }
    },
    [installPWA, navigate],
  );
}
