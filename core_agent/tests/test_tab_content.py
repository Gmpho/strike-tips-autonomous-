"""TAB manifest + Europe region scan: manifest-driven, never brute force."""
import pytest

from core_agent.skills.parsers.tab_content import (
    parse_name,
    meetings_for_regions,
)


@pytest.mark.parametrize("filename,folder,meeting,region", [
    ("KEMPTON(UK)@2026.10.05.pdf", "", "kempton", "UK"),
    ("FAIRYHOUSE(IRE)@2026.10.05.pdf", "", "fairyhouse", "IRE"),
    ("DEAUVILLE-LA TOUQUES(FRA)@2026.10.05.pdf", "", "deauville-la_touques", "FRA"),
    ("HOLLYWOODBETS DURBANVILLE@2026.10.07.pdf", "SouthAfrican", "hollywoodbets_durbanville", "SA"),
    ("BIPOT QUICKMIX@2026.10.05.pdf", "SouthAfrican", "bipot_quickmix", "SA"),
    ("garbage", "", "garbage", ""),
])
def test_parse_name(filename, folder, meeting, region):
    got = parse_name(filename, folder)
    assert got["meeting"] == meeting
    assert got["region"] == region


def test_meetings_for_regions_filters_and_dedupes():
    manifest = {"cards": [
        {"meeting": "kempton", "region": "UK", "date": "2026.10.05", "path": "a"},
        {"meeting": "kempton", "region": "UK", "date": "2026.10.05", "path": "a"},
        {"meeting": "vaal", "region": "", "date": "2026.10.05", "path": "b"},
        {"meeting": "fairyhouse", "region": "IRE", "date": "2026.10.05", "path": "c"},
    ]}
    got = meetings_for_regions(manifest, ["uk", "ire"])
    assert sorted(m["meeting"] for m in got) == ["fairyhouse", "kempton"]
    # unknown-region entries never scan
    assert all(m["region"] for m in got)


@pytest.mark.asyncio
async def test_run_region_scan_uses_manifest_only(monkeypatch):
    """Europe scan touches only manifest meetings — no 84-track sweep."""
    from core_agent.core.strike_tips import StrikeTips
    import core_agent.skills.parsers.tab_content as tc

    seen = []

    async def fake_manifest(day=None):
        return {"cards": [
            {"meeting": "kempton", "region": "UK", "date": "2026.10.05", "path": "p"},
            {"meeting": "vaal", "region": "", "date": "2026.10.05", "path": "q"},
        ]}

    monkeypatch.setattr(tc, "fetch_manifest", fake_manifest)

    sent = {}

    class FakeTelegram:
        async def send_daily_tips(self, results, title="Daily Intelligence Report"):
            sent["title"] = title
            sent["tracks"] = sorted(results.keys())
            return True

    strike = StrikeTips.__new__(StrikeTips)
    strike.telegram = FakeTelegram()
    strike.data_dir = "/tmp"

    async def fake_scrape(track, date_str=None):
        seen.append(track)
        return [{"track": track, "race_number": 1, "value_bets": []}]

    strike.scrape_and_analyze_track = fake_scrape
    out = await strike.run_region_scan(["UK", "IRE"])
    assert seen == ["kempton"]  # vaal (no region) excluded
    assert sent["title"] == "Europe Intelligence Report"
    assert out["meetings_scanned"] == 1
    assert out["total_value_bets"] == 0


@pytest.mark.asyncio
async def test_run_region_scan_alerts_no_stake(tmp_path, monkeypatch):
    """Stage 2: individual Europe alerts fire with stake 0.00, gates honored."""
    from core_agent.core.strike_tips import StrikeTips
    import core_agent.skills.parsers.tab_content as tc

    async def fake_manifest(day=None):
        return {"cards": [
            {"meeting": "kempton", "region": "UK", "date": "2026.10.05", "path": "p"},
        ]}

    monkeypatch.setattr(tc, "fetch_manifest", fake_manifest)

    alerts = []

    class FakeTelegram:
        async def send_daily_tips(self, results, title="Daily Intelligence Report"):
            return True

        async def send_value_bet(self, **kw):
            alerts.append(kw)
            return True

    strike = StrikeTips.__new__(StrikeTips)
    strike.telegram = FakeTelegram()
    strike.data_dir = str(tmp_path)  # no settings.json -> defaults: enabled, no priority filter

    async def fake_scrape(track, date_str=None):
        return [{"track": track, "race_number": 3, "race_time": "15:20",
                 "value_bets": [
                     {"horse": "H1", "edge_percent": 16.0, "odds_decimal": 4.0},
                     {"horse": "", "edge_percent": 20.0, "odds_decimal": 5.0},
                 ]}]

    strike.scrape_and_analyze_track = fake_scrape
    out = await strike.run_region_scan(["UK"])
    assert out["total_value_bets"] == 2
    assert len(alerts) == 1  # nameless entry skipped
    assert alerts[0]["stake"] == 0.0
    assert alerts[0]["confidence"] == "STRONG_VALUE"
    assert alerts[0]["ref"].startswith("EUR-")


@pytest.mark.asyncio
async def test_region_scan_quality_gate(monkeypatch, tmp_path):
    """135-flag firehose fix: edge floor + top-N per race."""
    from core_agent.core.strike_tips import StrikeTips
    import core_agent.skills.parsers.tab_content as tc

    async def fake_manifest(day=None):
        return {"cards": [
            {"meeting": "kempton", "region": "UK", "date": "2026.10.06", "path": "p"},
        ]}

    monkeypatch.setattr(tc, "fetch_manifest", fake_manifest)

    class FakeTelegram:
        async def send_daily_tips(self, results, title="Daily Intelligence Report"):
            return True

        async def send_value_bet(self, **kw):
            return True

    strike = StrikeTips.__new__(StrikeTips)
    strike.telegram = FakeTelegram()
    strike.data_dir = str(tmp_path)

    async def fake_scrape(track, date_str=None):
        return [{"track": track, "race_number": 1, "race_time": "14:00",
                 "value_bets": [
                     {"horse": "A", "edge_percent": 12.0, "odds_decimal": 5.0},
                     {"horse": "B", "edge_percent": 8.0, "odds_decimal": 6.0},
                     {"horse": "C", "edge_percent": 6.0, "odds_decimal": 7.0},
                     {"horse": "D", "edge_percent": 0.1, "odds_decimal": 30.0},
                 ]}]

    strike.scrape_and_analyze_track = fake_scrape
    out = await strike.run_region_scan(["UK"], min_edge=5.0, max_per_race=2)
    kept = out["results"]["kempton"][0]["value_bets"]
    assert [v["horse"] for v in kept] == ["A", "B"]  # floor + top-2, ordered
    assert out["total_value_bets"] == 2
