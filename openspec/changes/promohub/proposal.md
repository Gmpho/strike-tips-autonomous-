# Proposal: PromoHub Campaigns

Convert curious signups into linked core users with Betway-style promos,
restrained: carousel + contextual nudges, 7-day snooze, never over betting flows.

## Scope
- `src/lib/campaigns.ts`: definitions, targeting engine, snooze store, telemetry.
- `src/components/promos/`: PromoCard, PromoCarousel, SettingsNudge, ExoticsIntro, SupportSlot.
- Wiring: dashboard carousel slot, Settings telegram row, Exotics Hub intro.
- Launch campaigns: PWA install, Telegram connect, exotics intro, support slot.
