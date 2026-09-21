# Tasks: Telegram HUD UX Alignment & Rich Formatting

- [x] Create `core_agent/agent/telegram_format.py` with `escape_html()`, `markdown_to_telegram_html()`, `format_race_card_for_telegram()`, and `split_for_telegram()` <!-- id: 0 -->
- [x] Create unit tests in `core_agent/tests/test_telegram_format.py` covering HTML escaping, markdown conversion, race card table formatting, and text splitting <!-- id: 1 -->
- [x] Update `core_agent/core/modal_app.py` webhook path to add typing loop, HTML conversion, race card table formatting, paragraph chunking, and `/status` summary table <!-- id: 2 -->
- [x] Update `core_agent/channels/telegram.py` polling path to add typing loop, HTML conversion, race card table formatting, and paragraph chunking <!-- id: 3 -->
- [x] Run test suite (`pytest core_agent/tests/test_telegram_format.py`) and verify zero failures <!-- id: 4 -->
