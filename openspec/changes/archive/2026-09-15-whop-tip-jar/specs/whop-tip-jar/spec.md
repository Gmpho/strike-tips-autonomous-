## Purpose

Voluntary community funding with zero paywalls: tips stay free, supporters chip in once-off.

## ADDED Requirements

### Requirement: Whop products and links

A `Keep Strike Tips Running` product SHALL offer three one-time plans (Coffee $3, Stable $9, Champion $17 with $55 strikethrough, adaptive pricing) with direct purchase URLs documented in `docs/WHOP_TIP_JAR.md`.

#### Scenario: Checkout links resolve
- **WHEN** any of the three purchase URLs is opened
- **THEN** Whop returns HTTP 200 with the correct plan

### Requirement: Single support surface

The HUD SHALL expose exactly one support surface: the `/support` page (footer link, SPA-routed) with the 3-up pricing cards, SAVE badge, costs line, and test-mode banner.

#### Scenario: Footer has one Support entry
- **WHEN** the footer renders
- **THEN** exactly one Support link exists, pointing at `/support`

### Requirement: Legal coverage for donations

Terms (§5 contributions, §7 AGPL, §9 liability cap), FAQ (cost/refund/influence), and Disclaimer (donations block) SHALL describe voluntary once-off donations, all versioned 1.1 / September 2026.

#### Scenario: Terms version
- **WHEN** `/terms` loads
- **THEN** it shows Version 1.1 with the contributions clause
