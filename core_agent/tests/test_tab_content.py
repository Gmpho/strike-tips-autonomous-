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

    async def fake_scrape(track, date_str=None):
        seen.append(track)
        return [{"track": track, "race_number": 1, "value_bets": []}]

    strike.scrape_and_analyze_track = fake_scrape
    out = await strike.run_region_scan(["UK", "IRE"])
    assert seen == ["kempton"]  # vaal (no region) excluded
    assert sent["title"] == "Europe Intelligence Report"
    assert out["meetings_scanned"] == 1
    assert out["total_value_bets"] == 0
