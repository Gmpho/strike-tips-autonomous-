# Design: Telegram HUD UX Alignment & Rich Formatting

## Architecture & Data Flow

```
Inbound Message (Webhook or Polling)
         │
         ▼
  Start Async Typing Loop (sendChatAction "typing" every 4s)
         │
         ▼
  AI Pipeline / Intent Router Processing
         │
         ▼
  Cancel Typing Loop
         │
         ▼
  Shared Telegram Formatter (core_agent/agent/telegram_format.py)
    ├── Race Card Detection → format_race_card_for_telegram (<pre> table)
    ├── Markdown Converter → markdown_to_telegram_html (<b>, <i>, <code>, <blockquote>)
    └── Message Splitter → split_for_telegram (<=3800 chars)
         │
         ▼
  Send via Telegram API (parse_mode="HTML", with plain-text retry fallback)
```

## Detailed Components

### 1. `core_agent/agent/telegram_format.py`
- `escape_html(text)`: Replaces `&`, `<`, `>`.
- `markdown_to_telegram_html(md_text)`: Line/block parser for headers, blockquotes, code blocks, bold, italic, and bullet list items.
- `format_race_card_for_telegram(text)`: Pattern matches race headers and runner lines (`1. Name — Odds — Form...`), building formatted monospace table.
- `split_for_telegram(text, max_length=3800)`: Paragraph chunker.

### 2. `core_agent/core/modal_app.py`
- Async typing task loop during bus query wait.
- `_send()` function updated to run formatter, HTML mode, and chunked delivery.
- `/status` command output formatted into clean emoji table.

### 3. `core_agent/channels/telegram.py`
- Rate-limited typing indicator task per chat during processing.
- `_send_loop` updated to use `markdown_to_telegram_html`, `format_race_card_for_telegram`, and `split_for_telegram`.
