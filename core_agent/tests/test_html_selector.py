"""bs4 adapter + ported parsers: no scrapling, no browser, same output."""

from core_agent.core.html_selector import Selector
from core_agent.skills.parsers.racing_odds_api import RacingOddsAPI

DAILY_HTML = b"""
<html><body>
<a href="/daily/kempton/05-November-2026/14-20">14:20 Kempton</a>
<a href="/daily/kempton/05-November-2026/14-55">14:55 Kempton</a>
<a href="/daily/other/link">not a race</a>
</body></html>
"""

RACE_HTML = b"""
<html><body>
<div class="ro-runners">
  <div class="ro-racecard">
    <div class="ro-racecard__name">1. Arishka's Dream</div>
    <div class="ro-racecard__detail">
      <div class="ro-racecard__odds">
        <a href="/go/megapari">5/2 \xe2\x86\x97</a>
        <a href="/go/melbet">3/1</a>
      </div>
    </div>
  </div>
  <div class="ro-racecard">
    <div class="ro-racecard__name">2. No Prices</div>
    <div class="ro-racecard__detail"><div class="ro-racecard__odds"></div></div>
  </div>
</div>
</body></html>
"""


def test_adapter_exposes_scrapling_surface():
    sel = Selector("<div class='x'><a href='/go/a'> 5/2 </a></div>", auto_save=True, adaptive=True)
    divs = sel.css(".x")
    assert len(divs) == 1
    assert divs[0].tag == "div"
    links = divs[0].css("a")
    assert links[0].attrib["href"] == "/go/a"
    assert links[0].get_all_text(strip=True) == "5/2"


def test_adapter_handles_class_lists_in_attrib():
    sel = Selector('<a class="h7 a--plain tooltip" href="/x">Go</a>')
    link = sel.css("a")[0]
    assert link.attrib["class"] == "h7 a--plain tooltip"


def test_racing_odds_daily_parsing_without_scrapling():
    races = RacingOddsAPI()._parse_daily(DAILY_HTML)
    assert [r["course"] for r in races] == ["Kempton", "Kempton"]
    assert races[0]["time"] == "14-20"
    assert races[0]["race_time_display"] == "14:20 Kempton"


def test_racing_odds_detail_parsing_without_scrapling():
    horses = RacingOddsAPI()._parse_race_detail(RACE_HTML)
    assert len(horses) == 1
    assert horses[0]["name"] == "Arishka's Dream"
    assert horses[0]["bookmakers"] == {"megapari": 3.5, "melbet": 4.0}
    assert horses[0]["odds_decimal"] == 3.5
