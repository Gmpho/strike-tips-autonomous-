## Why

Infra costs are real but tiny (~$5/mo); a voluntary tip-jar funds them without paywalls, keeping tips free forever and trust compounding. Whop handles payment/KYC so no card code is written.

## What Changes

* Whop product `Keep Strike Tips Running` + 3 one-time plans ($3/$9/$17, adaptive pricing, $55 strikethrough on Champion) with direct purchase URLs.
* HUD: footer ☕ button → 3-up pricing modal (featured Champion, SAVE badge, checklist, why-box) + full `/support` page + footer link.
* Legal: Terms §5/IP/liability, FAQ cost Q&As, Disclaimer donations block (v1.1, Sep-2026).
* Docs: `docs/WHOP_TIP_JAR.md` (IDs, CLI, go-live checklist, Telegram copy); README support line.
* Test mode throughout; single-flag flip (`SUPPORT_TEST_MODE`) + rebuild for go-live.

## Capabilities

### New Capabilities
- `whop-tip-jar`: product/plans/links, support UI, legal coverage, docs.

### Modified Capabilities
- (none)

## Impact

* New: `lib/support.ts`, `SupportPanel.tsx`, `pages/SupportPage.tsx`, `docs/WHOP_TIP_JAR.md`
* Modified: `App.tsx` (route), `Footer.tsx` (links), Terms/FAQ/Disclaimer pages, README
* Secrets: none (Whop-hosted checkout; no keys in repo or bundle)
