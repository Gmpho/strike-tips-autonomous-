"""Track -> region resolution (mirrors strike-tips-hud/src/lib/regions.ts)."""
from __future__ import annotations

import re


_SA = {
    "turffontein", "vaal", "fairview", "scottsville", "kenilworth",
    "greyville", "durbanville", "clairwood",
}
_UK_IE = {
    "cheltenham", "ascot", "newmarket", "goodwood", "epsom", "york",
    "southwell", "leopardstown", "curragh", "fairyhouse", "punchestown",
    "galway", "naas", "tipperary", "clonmel", "musselburgh", "kelso",
    "beverley", "lingfield", "sandown", "chester", "haydock", "aintree",
    "kempton", "newcastle", "wolverhampton", "yarmouth", "bath",
    "doncaster", "redcar", "uttoxeter", "nottingham", "chepstow", "wexford",
    "dundalk",
    # Nov-2026: TAB serves these weekly but they were missing, so their
    # tickets resolved to "OTHER" and the HUD's jurisdiction filter hid them.
    "huntingdon", "catterick", "fakenham", "plumpton", "hereford", "exeter",
    "taunton", "warwick", "ludlow", "sedgefield", "cartmel", "newbury",
    "salisbury", "windsor", "brighton", "leicester", "ripon", "thirsk",
    "hamilton", "ayr", "perth", "fontwell", "chelmsford", "towcester",
    # Irish tracks from the same gap.
    "down royal", "downpatrick", "bellewstown", "killarney", "roscommon",
    "ballinrobe", "limerick", "tramore", "cork", "listowel", "navan",
}
_HK = {"sha tin", "shatin", "happy valley"}
_JP = {"tokyo", "nakayama", "kyoto", "kanazawa", "mombetsu", "monbetsu",
       "nagoya", "ohi", "kochi", "mizusawa", "urawa", "funabashi",
       "kawasaki", "sonoda", "saga", "morioka", "himeji", "oi", "chukyo",
       "hanshin"}
_AUS = {"flemington", "randwick", "caulfield", "moonee valley", "rosehill",
        "eagle farm", "morphettville", "belmont", "ascot perth", "balaklava",
        "canterbury", "doomben", "launceston", "shepparton", "globe derby",
        "gloucester park"}
_USA = {"churchill downs", "santa anita", "belmont park", "saratoga",
        "parx racing", "finger lakes", "mahoning valley", "mountaineer",
        "charles town", "lone star", "remington park", "delta downs",
        "penn national", "horseshoe indianapolis", "woodbine"}
# woodbine is CAN per HUD but grouped here for simplicity; override below
_CAN = {"woodbine"}
# Gulf (Nov-2026): the Betfair exchange feed carries Bahrain (group "BAH")
# and ATR's results cover Abu Dhabi, but neither venue was in any map — so
# every Gulf race resolved to "OTHER" and was dropped by the region filters
# before it could reach the card.
_UAE = {"abu dhabi", "dubai", "meydan", "jebel ali", "al ain"}
_BHR = {"bahrain", "sakhir"}


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip().lower())


def _base(name: str) -> str:
    """The venue without its country suffix: "Abu Dhabi (UAE)" -> "abu dhabi".

    Only the Gulf lookup uses this. The suffix is how ATR names its courses
    ("Kenilworth (RSA)"), and the Gulf venues reach us in both forms —
    Betfair says "Bahrain", ATR says "Abu Dhabi (UAE)".
    """
    return re.sub(r"\s*\([^)]*\)", " ", str(name or "")).strip().lower()


def region_of(track: str) -> str:
    t = _norm(track)
    if t in _SA:
        return "SA"
    if t in _HK:
        return "HK"
    if t in _JP:
        return "JP"
    if t in _AUS:
        return "AUS"
    if t in _CAN:
        return "CAN"
    if t in _UAE or _base(t) in _UAE:
        return "UAE"
    if t in _BHR or _base(t) in _BHR:
        return "BHR"
    if t in _USA:
        return "USA"
    if t in _UK_IE:
        return "UK_IE"
    return "OTHER"


def region_label(code: str) -> str:
    return {
        "SA": "South Africa", "UK_IE": "UK & Ireland", "HK": "Hong Kong",
        "JP": "Japan", "AUS": "Australia", "CAN": "Canada", "USA": "USA",
        "FRA": "France", "UAE": "United Arab Emirates", "BHR": "Bahrain",
        "OTHER": "Other",
    }.get(code, code)