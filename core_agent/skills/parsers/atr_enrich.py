"""ATR snapshot enrichment (Oct-2026 course-context work).

ATR omits meeting context that the live snapshot already holds. This module
backfills missing course/time onto movers + predictions by matching horse
names against snapshot runners. ATR-parsed values always win — enrichment
only fills blanks, never overwrites.
"""
from __future__ import annotations

import logging
from typing import Dict, List

logger = logging.getLogger("atr-enrich")


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


def build_runner_index(snapshot_events: Dict) -> Dict[str, Dict]:
    """Snapshot events -> normalized horse name -> {course, time, odds}."""
    index: Dict[str, Dict] = {}
    for ev in (snapshot_events or {}).values():
        course = ev.get("course") or ev.get("venue") or ""
        t = ev.get("start_time") or ev.get("time") or ""
        for r in ev.get("runners", []) or []:
            name = r.get("name", "")
            key = _norm(name)
            if key and key not in index:
                index[key] = {
                    "course": course,
                    "time": t,
                    "odds": r.get("outcomeName") or r.get("odds"),
                }
    return index


def attach_snapshot_context(entries: List[Dict], snapshot_events: Dict) -> List[Dict]:
    """Fill blank course/time on ATR entries from the snapshot index."""
    if not entries or not snapshot_events:
        return entries
    index = build_runner_index(snapshot_events)
    filled = 0
    for e in entries:
        if e.get("course") and e.get("time"):
            continue
        hit = index.get(_norm(e.get("horse", "")))
        if not hit:
            continue
        if not e.get("course") and hit.get("course"):
            e["course"] = hit["course"]
            filled += 1
        if not e.get("time") and hit.get("time"):
            e["time"] = hit["time"]
    if filled:
        logger.info("ATR enrich: backfilled course on %d entries", filled)
    return entries
