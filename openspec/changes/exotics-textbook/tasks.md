# Tasks: Exotics Textbook + Tracks

## 1. Research

- [x] 1.1 TAB pool rules from source (tab.co.za, TABGOLD policy): legs, minimums, fractional, Pick 3 rolling status, Quartet entry types
- [x] 1.2 Track biases from source (Sporting Post, Citizen/Piere Strydom, Computaform course data, racehorseowners.co.za)
- [x] 1.3 Flamingo Park status verified CLOSED (Jul-2020) — excluded from bundle

## 2. OKF content

- [x] 2.1 `strategies/exotics-pools.md` (full shelf: JP/P6/PA/BI/Pick3/Double + Exacta/Trifecta/Quartet/Swinger)
- [x] 2.2 `strategies/exotics-construction.md` (banker/saver economics, widen-the-murk, concentrate-vs-spread, per-pool patterns, scratchings)
- [x] 2.3 `strategies/exotics-case-friday-night.md` (Phutulicious: coverage vs insight)
- [x] 2.4 Punter-rules appended to all 7 track files (turffontein, vaal, kenilworth, scottsville, durbanville, greyville, fairview)
- [x] 2.5 Bundle rebuilt: 15 entries, search-verified

## 3. Builder doctrine

- [x] 3.1 `leg_uncertainty` + `widen_murkiest_legs` + `apply_flagged_horses` + `race_suitability`
- [x] 3.2 `test_exotics_doctrine.py` green (doctrine + bundle presence)

## 4. Ship (blocked on user: no deploy until tests done)

- [ ] 4.1 Full backend suite green (docker up) + `npm run build`
- [ ] 4.2 Edge deploy (`npm run deploy` in cloudflare_mcp_edge) — textbook live on worker
- [ ] 4.3 Live MCP search check: "jackpot" ranks exotics-pools first
