import { useEffect } from 'react';

declare global {
  interface Window {
    Telegram?: any;
  }
}

export function useTelegram() {
  const tg = window.Telegram?.WebApp;

  useEffect(() => {
    if (tg) {
      tg.ready();
      tg.expand();
      
      // Adapt theme
      const colorScheme = tg.colorScheme;
      const themeParams = tg.themeParams;
      
      if (colorScheme === 'dark') {
        document.documentElement.classList.add('dark');
      } else {
        document.documentElement.classList.remove('dark');
      }
      
      // Update CSS variables based on Telegram theme
      if (themeParams.bg_color) {
        document.documentElement.style.setProperty('--tg-bg-color', themeParams.bg_color);
      }
      if (themeParams.text_color) {
        document.documentElement.style.setProperty('--tg-text-color', themeParams.text_color);
      }
    }
  }, [tg]);

  return {
    tg,
    user: tg?.initDataUnsafe?.user,
    queryId: tg?.initDataUnsafe?.query_id,
    close: () => tg?.close(),
    ready: () => tg?.ready(),
    expand: () => tg?.expand(),
    MainButton: tg?.MainButton,
    BackButton: tg?.BackButton,
    HapticFeedback: tg?.HapticFeedback,
  };
}
