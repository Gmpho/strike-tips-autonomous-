# Proposal: Telegram HUD UX Alignment & Rich Formatting

## Why
Upgrade Telegram interaction across both webhook (`modal_app.py`) and polling (`channels/telegram.py`) send paths so the bot feels like the HUD:
- Active typing indicator loop (`sendChatAction("typing")`) while AI pipeline executes.
- Rich HTML mode formatting converter (`markdown_to_telegram_html`) replacing legacy Markdown parse mode to eliminate parse errors and formatting losses.
- Monospace `<pre>` table layout for pasted race cards (`format_race_card_for_telegram`).
- Safe paragraph-boundary splitting (`split_for_telegram`) for long analyses.
- Rich status table for `/status` command.

## What Changes
- Create `core_agent/agent/telegram_format.py` (shared formatter module)
- Update `core_agent/core/modal_app.py` (webhook path)
- Update `core_agent/channels/telegram.py` (polling path)
- Create `core_agent/tests/test_telegram_format.py` (unit tests and integration pins)
