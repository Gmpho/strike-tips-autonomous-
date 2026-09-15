# ☕ Whop Tip-Jar — Community Funding for Strike Tips

Tips stay free forever. This is a voluntary, once-off tip-jar covering
hosting, domains, and compute — no paywalls, no premium tiers, no perks owed.

## Product

| Item | ID / Value |
|---|---|
| Product | `Keep Strike Tips Running` (`prod_ukwXZTvjTAhn4`, route `keep-strike-tips-running`) |
| ☕ Coffee | `$3 once-off` (`plan_d5bSGrdp0tbz1`) → https://whop.com/checkout/plan_d5bSGrdp0tbz1 |
| 🏇 Stable | `$9 once-off` (`plan_602get0jKk7jP`) → https://whop.com/checkout/plan_602get0jKk7jP |
| 🏆 Champion | `$17 once-off`, strike-through `$55` (`plan_CovHg20PdhfJn`) → https://whop.com/checkout/plan_CovHg20PdhfJn |

- Plans are `one_time`, currency `usd` (lowercase — the API rejects `USD`/`ZAR`).
- `adaptive_pricing_enabled` lets SA buyers pay a localised amount.
- `strike_through_initial_price: 55` on Champion renders the anchor natively.
- Each plan exposes a direct `purchase_url` — no checkout-configuration objects needed.

## HUD wiring

- `strike-tips-hud/src/lib/support.ts` — tier data, links, `SUPPORT_TEST_MODE` flag.
- `SupportPanel.tsx` — footer ☕ button → 3-up pricing modal (featured Champion).
- `pages/SupportPage.tsx` — full page at `/support` (footer link, SPA fallback covers routing).
- To flip test → live: set `SUPPORT_TEST_MODE = false`, rebuild, redeploy. Links are unchanged (test/live is account-side).

## CLI cheat sheet

```bash
whop products list
whop plans list
whop plans get <plan_id>
whop plans update <plan_id> --description "..." --adaptive_pricing_enabled
whop stats   # totals anytime
```

Idempotency keys used: `strike-tips-jar-001`, `strike-jar4-*`. Reuse new keys per attempt — a consumed key with different params 400s.

## Go-live checklist (owner)

1. Whop dashboard → payouts: bank details + identity verification (KYC).
2. Flip test mode off (account-side) + `SUPPORT_TEST_MODE = false` → rebuild → deploy.
3. Send a real R-amount test payment to yourself; confirm payout lands.
4. Announce in Telegram (pinned message copy below).

## Telegram copy

> 🏇 *Strike Tips stays free forever.* If the machine's made you money and you'd like to keep the lights on — once-off, no subscriptions, no paywalls, ever:
> ☕ Coffee $3 · 🏇 Stable $9 · 🏆 Champion $17 (SAVE $38)
> 👉 https://strike-tips-hud.pages.dev/support

## Legal coverage

Terms §5 (voluntary contributions), FAQ (cost/refund/influence Q&As), and Disclaimer (donations warning block) were updated Sep-2026 (v1.1). Keep them in sync if tiers change.

## Phase 2 (only if donations grow)

Supporters wall: `payment.succeeded` webhook → Modal endpoint → HUD wall. Needs endpoint + stored list + refund/anonymous handling. Not built — deliberately.
