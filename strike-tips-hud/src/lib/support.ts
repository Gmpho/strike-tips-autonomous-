// Community tip-jar links (Whop-hosted checkout — our domain never touches
// payment). Flip TEST_MODE to false after payouts/KYC go live; links stay
// identical (Whop test vs live is account-side).
export const SUPPORT_TEST_MODE = false;

export interface SupportTier {
  key: string;
  name: string;
  price: string;
  approx: string;
  strike?: string;
  saveBadge?: string;
  blurb: string;
  url: string;
}

export const SUPPORT_TIERS: SupportTier[] = [
  {
    key: 'coffee',
    name: '☕ Coffee',
    price: '$3',
    approx: '≈R50 once-off',
    blurb: 'Buy the machine a coffee.',
    url: 'https://whop.com/checkout/plan_d5bSGrdp0tbz1',
  },
  {
    key: 'stable',
    name: '🏇 Stable',
    price: '$9',
    approx: '≈R150 once-off',
    blurb: 'Cover a month of infrastructure.',
    url: 'https://whop.com/checkout/plan_602get0jKk7jP',
  },
  {
    key: 'champion',
    name: '🏆 Champion',
    price: '$17',
    approx: '≈R300 once-off',
    strike: '$55',
    saveBadge: 'SAVE $38',
    blurb: 'Founding supporter fuel. Keeps the lights on for months.',
    url: 'https://whop.com/checkout/plan_CovHg20PdhfJn',
  },
];

export const SUPPORT_COSTS_LINE =
  'Domain + compute ≈ $5/mo. Tips stay free forever — chip in only if the machine made you money.';

export interface TierPerks {
  included: string[];
  excluded: string[];
  why?: string;
}

// Honest donation ladder: every rand funds the same infra; higher tiers
// cover more months. No paywalled features — tips stay free for everyone.
export const TIER_PERKS: Record<string, TierPerks> = {
  coffee: {
    included: ['Keeps tips free', 'Covers race-day compute'],
    excluded: ['A full month of infra', 'Founding status'],
  },
  stable: {
    included: ['Keeps tips free', 'Covers race-day compute', 'A full month of infra'],
    excluded: ['Founding status'],
  },
  champion: {
    included: ['Keeps tips free', 'Covers race-day compute', 'Months of infra + domain', 'Founding status'],
    excluded: [],
    why: 'One chip-in covers the project for months. The closest thing to a co-owner badge.',
  },
};
