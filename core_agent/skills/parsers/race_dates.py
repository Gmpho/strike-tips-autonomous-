"""Meeting-date helpers for racing feeds (no heavy imports).

TAB, 4RACING and the Computaform racecards all publish a track's NEXT
meeting well before it runs, so "today" is never a safe assumption about a
card. These helpers pull the meeting date out of a feed payload:

* :func:`program_date` — the live API's ``ProgramDate`` field.
* :func:`meeting_date_from_text` — a date printed on a racecard PDF.

Both return an ISO date or None (the source did not say).
"""
from __future__ import annotations

import re
from datetime import date as _date
from typing import Any, Dict, Optional

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5,
    "june": 6, "july": 7, "august": 8, "september": 9, "october": 10,
    "november": 11, "december": 12,
}

_TEXT_DATE = re.compile(
    r"\b(\d{1,2})\s+(January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\s+(\d{4})\b",
    re.IGNORECASE,
)


def program_date(program: Dict[str, Any]) -> Optional[str]:
    """The meeting date of a TAB program ("2026-11-13 00:00:00" -> ISO)."""
    raw = str((program or {}).get("ProgramDate") or "").strip()
    if not raw:
        return None
    head = raw.split(" ")[0].split("T")[0]
    try:
        return _date.fromisoformat(head).isoformat()
    except ValueError:
        return None


def meeting_date_from_text(
    raw_text: str, horizon_days: int = 90, past_days: int = 7
) -> Optional[str]:
    """The meeting date a racecard states ("14 November 2026" -> ISO).

    Best-effort: the first full date inside the window wins, so a stale date
    printed in a footer cannot beat the meeting header.
    """
    if not raw_text:
        return None
    today = _date.today()
    for m in _TEXT_DATE.finditer(str(raw_text)[:20000]):
        try:
            cand = _date(
                int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))
            )
        except ValueError:
            continue
        delta = (cand - today).days
        if -past_days <= delta <= horizon_days:
            return cand.isoformat()
    return None
