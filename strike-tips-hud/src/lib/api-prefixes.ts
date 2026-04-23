export const BETTING_API_PREFIX = '/api/betting';

export const BETTING_ENDPOINTS = {
  history: `${BETTING_API_PREFIX}/history`,
  open: `${BETTING_API_PREFIX}/open`,
  stats: `${BETTING_API_PREFIX}/stats`,
  accountSummary: `${BETTING_API_PREFIX}/account-summary`
} as const;
