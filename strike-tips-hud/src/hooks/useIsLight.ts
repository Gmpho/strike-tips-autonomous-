import { useEffect, useState } from 'react';

/**
 * True while the app is in light mode.
 *
 * ThemeToggle flips a `light` class on <html> and nothing else, so charts and
 * any colour decided in JS have to watch that class to stay readable.
 */
export function useIsLight(): boolean {
  const [isLight, setIsLight] = useState<boolean>(
    () => typeof document !== 'undefined' && document.documentElement.classList.contains('light'),
  );

  useEffect(() => {
    const root = document.documentElement;
    const sync = () => setIsLight(root.classList.contains('light'));
    sync();
    const observer = new MutationObserver(sync);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  return isLight;
}
