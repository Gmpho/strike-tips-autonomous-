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

## Member messages (copy-paste)

### 1. Current members (group announcement)

> 🏇 *Quick one, family.*
>
> Strike Tips stays **free forever** — that will never change. But the machine costs real money to keep alive (hosting, domains, compute), and until now that's come out of one pocket. 😅
>
> So there's now a voluntary tip-jar — **once-off, no subscriptions, no paywalls, no locked tips.** Only chip in if the machine's made you money:
>
> ☕ Coffee — $3 (≈R50)
> 🏇 Stable — $9 (≈R150)
> 🏆 Champion — $17 (≈R300, marked down from $55)
>
> 👉 https://strike-tips-hud.pages.dev/support
>
> Zero pressure. The tips don't change either way. 🙏

### 2. Gone members (win-back DM)

> Hey! 👋 Long time — Strike Tips has grown a lot since you left: auto-settling bets, bankroll analytics, a proper dashboard, the works. Still 100% free.
>
> I'm keeping it alive with a small voluntary tip-jar now (once-off, from $3 — only if you ever feel like it). No catch, just thought you'd want to see what it became:
>
> 👉 https://strike-tips-hud.pages.dev/support
>
> Door's always open. 🏇

### 3. New members (welcome + pinned message)

> Welcome to Strike Tips! 🏇 Quick orientation:
>
> 📊 Daily AI value bets + full racecards → Dashboard
> 💰 Auto-settled results + bankroll tracking → Bankroll
> 📈 Performance deep-dives → Analytics
>
> Everything is **free, forever** — no subscriptions, no paywalls. There's an optional once-off tip-jar if the machine ever makes you money (link below), but it changes nothing about what you get.
>
> ⚠️ Paper-trading education only. 18+. Winners know when to stop.
>
> ☕ Support (optional): https://strike-tips-hud.pages.dev/support

## Legal coverage

Terms §5 (voluntary contributions), FAQ (cost/refund/influence Q&As), and Disclaimer (donations warning block) were updated Sep-2026 (v1.1). Keep them in sync if tiers change.

## Phase 2 (only if donations grow)

Supporters wall: `payment.succeeded` webhook → Modal endpoint → HUD wall. Needs endpoint + stored list + refund/anonymous handling. Not built — deliberately.
