# Tasks: Composio Creation Tools

## 1. Adapter package

- [x] 1.1 Create `core_agent/integrations/__init__.py` + `composio_client.py` (`execute(slug, payload, account)` via CLI subprocess, JSON in/out, per-call timeout) and verify `python3 -c "import core_agent.integrations.composio_client"` succeeds
- [x] 1.2 Add pinned-slug allowlist (Sheets 4 + X post family after discovery) and verify unknown slugs raise without executing

## 2. Internal tools

- [x] 2.1 Implement `create_analysis_sheet`, `export_pnl_report`, `publish_tip_post` in `core_agent/tools/composio_tools.py` with fixed schemas and verify imports resolve
- [x] 2.2 Register the 3 names in `TOOL_REGISTRY` and verify no vendor slug appears in model-facing schemas
- [x] 2.3 Implement per-user daily post cap + 402 pause/alarm and verify cap blocks with friendly message (mocked executor)

## 3. Connect flow

- [ ] 3.1 Add `/connect x|google` Telegram branches returning the Connect Link; store mapping chat ID → account and verify mapping round-trips (mocked)
- [ ] 3.2 Wire fallback delivery (Telegram + Email) on any adapter failure and verify fallback fires in tests

## 4. Verification

- [x] 4.1 Run `pytest core_agent/tests/test_composio_tools.py` (mocked executor: arg shapes, failure mapping, cap logic) and verify green
- [ ] 4.2 Live proof on owner accounts: one sheet write + one X dry-run, then one live post; record log IDs
- [ ] 4.3 Run full `pytest core_agent/tests/` and verify no regressions; `openspec validate composio-creation-tools`
