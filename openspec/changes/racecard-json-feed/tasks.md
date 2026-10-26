# Tasks: racecard-json-feed

## 1. Install (user-approved, after Docker verification)
- [ ] 1.1 `nvm use 24.22.1` (already the default; REA needs ≥22.23.4/24.22.1)
- [ ] 1.2 `npx rea-agents setup --client opencode` — registers MCP + skill
- [ ] 1.3 Restart opencode; confirm the REA tools appear
- [ ] 1.4 `rea doctor --json` (or equivalent) reports a healthy install

## 2. Discovery (live SA meeting required)
- [ ] 2.1 Capture HAR: tab4racing racecard → Network → save all
- [ ] 2.2 Identify the `phumelelaV4` sub-action returning runners/weights/draws
- [ ] 2.3 Document method, params (track/date/meeting id), auth, response shape
- [ ] 2.4 Confirm it covers all six SA tracks in scope

## 3. Parser
- [ ] 3.1 New `core_agent/skills/parsers/racecard_api.py` → `ScrapedRace`/`ScrapedRunner`
- [ ] 3.2 Route through `compliance` policy client (honest UA, paced)
- [ ] 3.3 Keep `tab_pdf_mapper` as fallback for PDF-only meetings
- [ ] 3.4 Tests with a captured fixture (no network)

## 4. Guardrails
- [ ] 4.1 No stealth / challenge solving anywhere in the path
- [ ] 4.2 If gated: stop, report, do not escalate
