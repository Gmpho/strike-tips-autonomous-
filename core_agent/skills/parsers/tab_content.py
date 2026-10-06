"""TAB content manifest (Oct-2026 international work).

Front door for non-SA cards: one cheap JSON call lists what's carded today
(Computaform PDFs + race cards + tips per tag group) with direct Azure-blob
PDF links. Replaces the dead tab.co.za/api JSON schedule (HTML shell).
"""
from __future__ import annotations

import logging
import re
from typing import Dict, List

logger = logging.getLogger("tab-content")

BASE = ("https://totex-col.4racing.com/PRODUCTS/webservice/phumelelaV4"
        "/get/Content/4RACINGWEB_TAB")

TAG_GROUPS = {
    "computaform": "ComputaformSA,ComputaformUK,ComputaformIRE,ComputaformEX",
    "cards": "SouthAfrican,International,Small",
    "tips": "Tips,HongKong,France,Sweden",
}

# "KEMPTON(UK)@2026.10.05.pdf" -> ("kempton", "UK"); pool files like
# "BIPOT QUICKMIX@2026.10.05.pdf" carry no region — folder decides.
NAME_RE = re.compile(r"^(?P<meeting>.+?)(?:\((?P<region>[A-Z]{2,3})\))?@(?P<date>\d{4}\.\d{2}\.\d{2})\.pdf$", re.IGNORECASE)

# Blob folder -> region fallback when the filename carries none.
FOLDER_REGION = {
    "SouthAfrican": "SA",
    "International": "INTL",
}


def parse_name(filename: str, folder: str = "") -> Dict:
    """Split a TAB PDF filename into meeting/region/date. Never raises."""
    m = NAME_RE.match((filename or "").strip())
    if not m:
        return {"meeting": (filename or "").strip(), "region": FOLDER_REGION.get(folder, ""),
                "date": "", "path": ""}
    meeting = m.group("meeting").strip().lower().replace(" ", "_")
    return {"meeting": meeting, "region": (m.group("region") or "").upper()
            or FOLDER_REGION.get(folder, ""), "date": m.group("date"), "path": ""}


async def fetch_manifest(day: str | None = None) -> Dict[str, List[Dict]]:
    """Manifest per tag group for a day (YYYY-MM-DD, default TODAY SAST).

    SAST, not container UTC: at 00:00–02:00 SAST the UTC date is still
    yesterday (Oct-2026: pulled 10-05 cards at 2am on the 6th). Racing days
    are SAST days, always.
    """
    import httpx

    if day:
        day_iso = day
    else:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day_iso = datetime.now(ZoneInfo("Africa/Johannesburg")).date().isoformat()
    out: Dict[str, List[Dict]] = {}
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            for group, tags in TAG_GROUPS.items():
                url = (f"{BASE}?sub_action=getComputaform&tag={tags}&date={day_iso}")
                r = await client.get(url, headers={"Referer": "https://www.tab.co.za/"})
                items: List[Dict] = []
                if r.status_code == 200:
                    try:
                        data = r.json().get("data", {})
                    except Exception:
                        data = {}
                    for _tag, entries in (data or {}).items():
                        for e in entries or []:
                            parsed = parse_name(e.get("name", ""), _tag)
                            parsed["path"] = e.get("path", "")
                            parsed["tag"] = _tag
                            if parsed["date"] == day_iso.replace("-", "."):
                                items.append(parsed)
                out[group] = items
    except Exception as e:
        logger.warning("[TAB-CONTENT] manifest fetch failed LOUDLY: %r", e)
        return {}
    total = sum(len(v) for v in out.values())
    logger.info("[TAB-CONTENT] %s: %d dated entries", day_iso, total)
    return out


def meetings_for_regions(manifest: Dict[str, List[Dict]], regions: List[str]) -> List[Dict]:
    """Filter dated manifest entries to region codes (UK, IRE, FRA, SA...).

    Matching is substring on region so UK matches UK-only and callers can
    pass broad groups. UNKNOWN-region entries are excluded — scan the card,
    never the mystery.
    """
    wants = {r.upper() for r in regions}
    out = []
    for entries in manifest.values():
        for e in entries:
            if e.get("region", "").upper() in wants:
                out.append(e)
    seen, deduped = set(), []
    for e in out:
        key = (e["meeting"], e["date"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)
    return deduped
