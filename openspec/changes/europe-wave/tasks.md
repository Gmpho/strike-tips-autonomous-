# Tasks: Europe Wave

## 1. Manifest + discovery

- [x] 1.1 `tab_content.py`: manifest fetch/parse per tag group, loud failures
- [x] 1.2 `race_schedule.py`: dead URL retired, Betway international source

## 2. Scan + schedule

- [x] 2.1 `run_region_scan` (digest-only) + CLI `--region`
- [x] 2.2 `europe_scan` 12:30 SAST cron (4th of 5)
- [x] 2.3 `send_daily_tips` title param (Europe Intelligence Report)

## 3. Verify (no deploy per order)

- [x] 3.1 `test_tab_content.py` green (manifest, regions, region scan)
- [ ] 3.2 Docker backend suite (needs docker up)
- [ ] 3.3 Deploy backend on approval; verify 12:30 cron fires + digest lands
