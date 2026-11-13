// Which view does a URL mean?
//
// Pulled out of App.tsx so the aliases can be tested: a rename that breaks a
// shared link is a bad trade for a better word, and `/logs` and `/telemetry`
// are both bookmarked by operators.
//
// Run: node --test tests/routes.test.ts

export const LEGAL_VIEWS = [
  'privacy',
  'terms',
  'disclaimer',
  'how-to-bet',
  'faq',
  'betting-rules',
  'responsible',
  'contact',
  'support',
];

// Logged-out visitors may read support + legal pages (with a sign-in banner);
// every other view gates to the landing page.
export const PUBLIC_VIEWS = [...LEGAL_VIEWS, 'leaderboard'];

export const VALID_VIEWS = [
  'dashboard', 'agents', 'chat', 'podcast', 'tts', 'exotics', 'bankroll',
  'analytics', 'logs', 'settings', 'healing', 'vitals', 'dreaming', 'news',
  'telemetry', 'market-movers', 'predictor', 'results', 'simulator',
  'leaderboard', 'picks', 'profile',
  ...LEGAL_VIEWS,
];

/**
 * Old or friendlier URLs that resolve to a route id.
 *
 * `engine-ops` is the label users now see; `telemetry` stays the id so the
 * existing links and the saved-view localStorage value keep working.
 */
export const PATH_ALIASES: Record<string, string> = {
  'engine-ops': 'telemetry',
};

/**
 * Resolve a pathname to a view id.
 *
 * Order: exact match, then alias, then the remembered view, then dashboard.
 * An unknown path must never resolve to something surprising silently — the
 * remembered view is the user's own last choice, which is the honest default.
 */
export function viewFromPath(
  pathname: string,
  remembered?: string | null,
): string {
  const path = String(pathname || '').replace(/^\/+/, '').replace(/\/+$/, '');
  if (VALID_VIEWS.includes(path)) return path;
  const aliased = PATH_ALIASES[path];
  if (aliased && VALID_VIEWS.includes(aliased)) return aliased;
  if (remembered && VALID_VIEWS.includes(remembered)) return remembered;
  return 'dashboard';
}
