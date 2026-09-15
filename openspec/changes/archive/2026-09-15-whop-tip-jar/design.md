## Context

Donations must feel trustworthy (Hostinger-style pricing reference) without implying paywalls. Whop hosts all payment; the HUD only links out. Currency: API rejects `USD`/`ZAR`, lowercase `usd` works; adaptive pricing localises for SA buyers.

## Goals / Non-Goals

**Goals:** shippable test-mode jar, honest copy, legal coverage, one support surface.

**Non-Goals:** supporters wall / webhooks (Phase 2, only if donations grow); recurring plans.

## Decisions

* 3-up cards with featured Champion (dark gradient keeps white text in both themes — explicit white tokens, not theme tokens).
* Single `/support` page over modal+link duplication.
* Test/live is account-side; `SUPPORT_TEST_MODE` banner is the only code flip.
