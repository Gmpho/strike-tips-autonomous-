from __future__ import annotations
import asyncio
import re
import logging
from core_agent.core.strike_brain import brain

logger = logging.getLogger("context-builder")

MAX_CONTEXT_CHARS = 12000

# Trivial patterns — skip heavy context assembly for greetings/filler
_TRIVIAL_PATTERNS = re.compile(
    r"^(hey|hello|hi|howdy|sup|thanks|thank\s*(?:you|s)|ok(?:ay)?|yes|yeah|yep|no|nope|nah|"
    r"bye|goodbye|lol|lmao|nice|cool|great|awesome|"
    r"what'?s\s*up|how'?s\s*it\s*going|how\s+(?:are|r)\s*(?:you|u)|"
    r"good\s*(?:morning|afternoon|evening|day))"
    r"[\s!?.]*$",
    re.IGNORECASE,
)


class ContextBuilder:
    async def build(self, session_key: str, user_message: str, history: list[dict], intent: str | None) -> str:
        # FAST PATH: trivial/filler messages — skip heavy lookups
        msg = user_message.strip()
        if len(msg) < 30 and _TRIVIAL_PATTERNS.match(msg):
            return f"[QUERY]\n{user_message[:2000]}"

        parts = []

        try:
            from core_agent.skills.memory.honcho_memory import HonchoMemory
            honcho = HonchoMemory(user_id=session_key)
            user_context = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, honcho.get_context),
                timeout=3.0,
            )
            if user_context:
                parts.append(f"[USER MEMORY]\n{user_context[:1000]}")
        except Exception:
            pass

        try:
            if brain and brain.memory and brain.memory._is_ready:
                insights = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, brain.memory.search_form_insights, user_message, 3),
                    timeout=3.0,
                )
                if insights:
                    parts.append(f"[FORM INSIGHTS]\n{insights[:2000]}")
        except Exception:
            pass

        try:
            from core_agent.skills.search_service import search_racing
            # Trigger live DuckDuckGo search for real-time information
            search_res = await asyncio.wait_for(
                search_racing(user_message, limit=3),
                timeout=10.0,
            )
            if search_res and search_res.get("results"):
                lines = []
                for r in search_res["results"]:
                    lines.append(f"• {r.get('title','')} ({r.get('url','')}):\n  {r.get('snippet','')}")
                if lines:
                    parts.append(f"[WEB SEARCH RESULTS]\n" + "\n".join(lines)[:2000])
        except Exception:
            logger.exception("ContextBuilder web search failed")

        try:
            from core_agent.core.snapshot_cache import get_snapshot
            snap = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_snapshot),
                timeout=3.0,
            )
            if snap and snap.get("events"):
                summary = self._truncate_snapshot(snap, user_message)
                if summary:
                    parts.append(f"[LIVE SNAPSHOT]\n{summary[:3000]}")
        except Exception:
            pass

        if history:
            hist = "\n".join(f"{h['role']}: {h['content'][:300]}" for h in history[-6:])
            parts.append(f"[HISTORY]\n{hist}")

        parts.append(f"[QUERY]\n{user_message[:2000]}")

        result = "\n\n".join(parts)
        if len(result) > MAX_CONTEXT_CHARS:
            result = result[:MAX_CONTEXT_CHARS] + "\n...[truncated]"
        return result

    def _truncate_snapshot(self, snap: dict, user_message: str = "") -> str | None:
        events = snap.get("events", {})
        if not events:
            return None
        
        msg_lower = user_message.lower()
        matched_events = []
        other_events = []
        
        for ev in events.values():
            course = (ev.get("course") or ev.get("venue") or "").lower()
            if course and course in msg_lower:
                matched_events.append(ev)
            else:
                other_events.append(ev)
                
        # Prioritize matched events, then fill up to 8 events total
        prioritized = matched_events + other_events

        lines = [f"Today's races ({len(events)} events):"]
        for ev in prioritized[:8]:
            eid = ev.get("id", ev.get("en", "?"))
            name = ev.get("en", "?")
            course = ev.get("course", ev.get("venue", ""))
            t = ev.get("start_time", ev.get("time", ""))
            race_num = ev.get("raceNumber", "")
            lines.append(f"  Race {race_num}: {course} {t} ({eid})")
            runners = ev.get("runners", [])
            for r in runners[:5]:
                lines.append(
                    f"    {r.get('name','?')} | J:{r.get('jockeyName','?')} "
                    f"T:{r.get('trainerName','?')} W:{r.get('weight','?')} O:{r.get('outcomeName','?')}"
                )
        return "\n".join(lines)
