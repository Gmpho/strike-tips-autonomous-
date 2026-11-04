# Roadmap

## November 2026 — Predictor-first community ("Slipstream")

Source: Hollywoodbets Punters Challenge research (Oct-2026) + 30-day WhatsApp
group poll (closes ~Nov-2026). Spec to be written when the poll lands.

### What
1. **Race-day predictor** (core game, build first): one pick per race, locked
   5 min before R1. Scoring stolen from Punters Challenge (proven): points =
   field size for finish position + winner's SP as bonus. Free to play,
   Google login is the ticket.
2. **Slip wall** (social layer, build second): comment-style slip posts,
   2 photo-slips/user/day (DB-enforced), text unlimited. Spam armor: 3-report
   auto-hide, owner mod tools, 24h-old accounts can't post photos, SHA-256
   duplicate-image flag, links/phone numbers non-clickable, 10 posts/hour cap.
3. **Must-be-won weekly**: guaranteed prize (e.g. R500 airtime) to weekly
   predictor champ, funded from Support tiers. Supporters fund prizes, prizes
   drive players, players become supporters.
4. **Crews**: private mini-leaderboards — WhatsApp group becomes "Crew #1".

### Privacy/security (locked decisions)
- Display names derived (FirstName + LastInitial) or optional handle; full
  Google profile never stored in community tables.
- Verified board serves aggregates only — no endpoint returns another user's
  ledger. Stakes hidden by default, EXIF destroyed by re-encode upload.
- RLS owner-write/public-read, DB-enforced photo cap (transactional), signed
  per-user Storage paths, write-only reports, POPIA erasure self-serve.

### Sequencing
Poll result → openspec change → migration → predictor game → slip wall →
crews → PromoHub campaign → weekly cron.
