# Tasks: OpenClaw-Style Telegram

## 1. Soul + spec

- [x] 1.1 Write `core_agent/agent/SOUL.md` and verify content matches approved voice
- [x] 1.2 Scaffold `openspec/changes/telegram-openclaw-style/` (proposal/design/spec/tasks) and verify `openspec validate telegram-openclaw-style` passes

## 2. Guard fix

- [x] 2.1 Add search-intent negatives + drop generic nouns in `context.py`; verify new gate tests pass
- [x] 2.2 Load SOUL.md into the Telegram system prompt path only; verify HUD prompt unchanged

## 3. Tables

- [x] 3.1 Implement `markdown_table_to_pre()` in `telegram_format.py`; verify converter tests pass (pipes, alignment rows, chunk-spanning tables)
- [x] 3.2 Wire converter into webhook `_send` before chunking; verify fallback delivery intact
- [x] 3.3 Add compact/full table rule to system prompt + session preference; verify keyword tests pass
- [x] 3.4 Enrich execute-position prompt with draw/gear/days/pedigree; verify prompt test passes

## 4. Verify

- [x] 4.1 Run `pytest core_agent/tests/test_telegram_format.py core_agent/tests/test_settlement_chain.py` green
- [x] 4.2 Commit + push (no deploy without explicit request)
