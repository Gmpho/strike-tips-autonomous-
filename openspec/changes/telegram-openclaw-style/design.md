# Design: OpenClaw-Style Telegram

## Context
- Webhook path (`modal_app.py`) sends HTML mode with grapheme-safe 3800
  chunking; polling path (`channels/telegram.py`) similar. Both keep the
  Markdown-fallback delivery guarantee (per telegram-bot skill).
- OpenClaw guidance (Context7): default to Telegram HTML, monospace code
  blocks for tables, split long text automatically. We already do all
  three — the missing piece is model-output tables reaching `<pre>` form.
- `_CARD_NOUNS` (~30 words) + no search intent = snapshot on nearly every
  turn; system prompt then says "use snapshot, no tool needed".

## Goals
- Casual/search turns never carry the card; racing turns do.
- Every data answer renders as an ASCII table on Telegram.
- Compact default fits 360px phones (~50 monospace chars); full on demand.

## Decisions
- Negative regexes over another keyword list: `search (the )?web`,
  `google( it)?`, `look ?up`, `latest news`, `what('s| is) new` suppress
  the card AND set a search flag the loop honors by calling
  `search_racing_data` first.
- Converter handles GitHub pipe tables (with/without alignment row),
  strips the alignment row, pads columns, wraps in `<pre>`.
- Full-column preference stored in session metadata (pattern matches
  persisted model preference).
- SOUL.md lives in `core_agent/agent/`, loaded only for Telegram turns
  (HUD chat keeps its own voice).

## Risks
- Narrowing `_CARD_NOUNS` may under-trigger on terse racing queries
  ("R4 Kenilworth?") — mitigated: track names + race numbers + odds
  formats (`4.5`, `R4`) still trigger; tests pin both directions.
