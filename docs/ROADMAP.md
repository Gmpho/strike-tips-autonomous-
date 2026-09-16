# Strike Tips Roadmap

*Last updated: September 2026. Owner-reviewed; checkboxes flip as work lands.*

## Now — Community funding (shipping)

- [x] Whop tip-jar live in test mode (Coffee $3 / Stable $9 / Champion $17, adaptive pricing, $55 strikethrough)
- [x] `/support` page + footer link (single surface), legal v1.1 (Terms/FAQ/Disclaimer, Sep-2026)
- [x] Member intro messages (current / gone / new) — see `docs/WHOP_TIP_JAR.md`
- [ ] Go-live: payouts bank + KYC in Whop dashboard → flip `SUPPORT_TEST_MODE=false` → rebuild → live test payment (owner-gated)

## Next — Growth plays (marketing-ideas skill)

1. **Win-back sequence** — gone ~30 members. DM drafted (see WHOP_TIP_JAR.md). Send after a winning Saturday. *Cost: zero.*
2. **Admin affiliates** — enable 20–30% member-affiliate cut on Whop when ready (5-min job). Owner says when.
3. **Free-tool SEO** — Kelly stake-calculator page for organic punter traffic. Half-day build. *Not started.*
4. **Short-form video** — WON-settle screenshots + equity curve, 10 min/race day, owner-run. *Not started.*

## Next — Outreach (cold-email skill)

Expected reply rate ~5–10% cold: send 20, work 1–2 conversations. Personal name sender ("Gift"), never brand. One link max, no pricing in email 1.

### Email A — tipping-site owners (white-label sample card)

*Subject:* `your [...] page`

> Noticed your [Track, e.g. Turffontein] previews go up race-morning with no data behind them — guessing that's a time problem, not a priority problem.
>
> I run an open-source system that auto-builds full race cards with AI value analysis, settles results itself, and publishes a verified P&L (ours is sitting at ~[X]% ROI over [N] settled bets). Happy to white-label a daily card for [Site] so your previews carry form, odds movement, and proof.
>
> Worth seeing one sample card?

**Follow-up A1 (day 4, new angle — proof):**
*Subject:* `saturday's card`

> Quick follow-up with receipts: Saturday our system went [e.g. 3 from 5 value picks, +RXXX paper]. Full card + settled P&L here: [link].
>
> Still happy to run [Track] through it once for [Site] — you'd see exactly what your readers would get.

**Follow-up A2 breakup (day 10):**
*Subject:* `closing this out`

> Don't want to be the guy who follows up forever — closing this out on my side. If race previews ever become a priority, the sample-card offer stands.
>
> Good luck for the season.

### Email B — betting group admins (trial + rev-share whisper later)

*Subject:* `quick idea for [Group Name]`

> Saw [Group] is [observation, e.g. posting screenshots but settling arguments in the comments every Saturday].
>
> I built a free bot that auto-settles posted tips and tracks every member's P&L publicly — kills the "who's actually profitable?" fights. A few groups run it alongside their own picks.
>
> Open to a 2-week trial in [Group]? I set it up, you change nothing.

**Follow-up B1 (day 4, new angle — social proof):**
*Subject:* `re: [Group Name]`

> One more angle: [another group / our own 170-member channel] uses the settler to end the Saturday night arguments — every tip auto-graded, full ledger public by 8pm.
>
> Trial still open if you want it. One-line reply and I'll set it up.

**Follow-up B2 breakup (day 10):**
*Subject:* `all good`

> Leaving this with you — if the settle-arguments ever get old, you know where I am. No hard feelings either way.

*(Rev-share whisper lives in email 2 of a live thread, never in cold copy: "Oh — and there's a rev-share if any of your members chip into the project fund. Details if the trial lands.")*

### Outreach inputs needed (owner)

- [ ] Fresh proof numbers (settled count + ROI + win rate at send time)
- [ ] One real prospect for A (name + site + observation)
- [ ] One real prospect for B (name + group + observation)

## Later — B2B / SaaS (open-core, AGPL)

- Auth + workspaces → one design-partner tipping site (cheap/free) → Stripe → API/white-label as the revenue line.
- Triggers: public track record compounded for weeks + first inbound interest. Not before.

### Monetization: three doors, one engine (MCP-first)

The engine already serves all three — monetization just adds the cash register:

1. 🚪 **MCP access (lead with this)** — per-key quotas (e.g. 10k tool calls/mo). AI-native buyers (site owners, group admins) plug the 16 racing tools straight into Claude Desktop / Cursor / their bots in 60 seconds. Zero integration work for them, stickiest revenue (their agents get wired into your tools).
2. 🚪 **REST access (backup door)** — same quotas, raw JSON for developers and high-volume machine-to-machine (leaner than MCP's chatty protocol at odds-feed cadence). Costs nothing extra to offer.
3. 🚪 **White-label dashboard** — full site under their brand for non-technical buyers. Monthly fee.

Price list leads with MCP ("AI-native access, 3 tiers"), footnote: "REST available on all tiers." Reach over margin: MCP removes the customer's integration homework, so deals close faster than REST-only competitors.

### WordPress integration (for tipster sites, e.g. My Big Bets — warm lead, personal contact)

Site is WordPress. Three depths, pitch in this order:

- **(a) Embed (5 min).** One `<iframe>` of a white-labeled card page pasted into any WP page. Clunky on mobile, no styling inside — fallback only.
- **(b) Auto-publish (the pitch).** Backend POSTs the finished morning card into their WordPress via REST API as a drafted/scheduled post. They wake up, review, publish. Zero routine change, hours back daily. Offer as a free one-meeting trial ("let Thursday's card publish itself, compare against yours").
- **(c) Plugin (only if it sticks).** Tiny WP plugin for live odds / settled-P&L widgets. Real dev work — after (b) proves the relationship.



## Later — Infra (spend-triggered only)

- OpenTofu for VPS (Ollama GPU box / Redis) if Modal passes ~€15/mo sustained.
- Never Terraform for Modal itself (`modal_app.py` IS the IaC); orchestrate both from CI.
- Trigger: the Telegram spend-report ping twitching — not before.
