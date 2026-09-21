from __future__ import annotations
import asyncio
import re
import logging
from core_agent.core.strike_brain import brain

logger = logging.getLogger("context-builder")

MAX_CONTEXT_CHARS = 12000

# Trivial patterns — skip heavy context assembly for greetings/filler.
# Sep-2026: "You good" / "What model are you" were NOT matched, so every
# conversational turn carried the full race card and the model parroted
# meetings back mid-chat ("You good" → "36 races across 7 tracks"). Now
# identity/meta/casual turns take the fast path too.
_TRIVIAL_PATTERNS = re.compile(
    r"^(hey|hello|hi|howdy|sup|thanks|thank\s*(?:you|s)|ok(?:ay)?|yes|yeah|yep|no|nope|nah|"
    r"bye|goodbye|lol|lmao|nice|cool|great|awesome|perfect|"
    r"you\s+good|u\s+good|all\s+good|you\s+ok(?:ay)?|you\s+there|"
    r"what'?s\s*up|how'?s\s*it\s*going|how\s+(?:are|r)\s*(?:you|u)|how\s+you|"
    r"who\s+are\s+you|what\s+are\s+you|what\s+model(?:\s+are\s+you)?|which\s+model|"
    r"what\s+(?:can|do)\s+you\s+do|what\s+do\s+you\s+offer|"
    r"good\s*(?:morning|afternoon|evening|day))"
    r"[\s!?.]*$",
    re.IGNORECASE,
)

# Card-intent gate. Heavyweight racing context (live snapshot, web search)
# attaches ONLY when the turn is actually about race data — or carries a
# pasted card (odds/Form:/Off Time fields), which is an analysis request.
_CARD_NOUNS = (
    "race", "card", "meeting", "odds", "runner", "field", "track",
    "today", "tomorrow", "value", "tip", "selection", "pick", "form",
    "jockey", "trainer", "exotic", "bipot", "pick 6", "jackpot",
    "place accumulator", "handicap", "stake", "edge", "betting", "bet",
    "favourite", "favorite", "winner", "going", "draw", "carlisle",
)
_PASTED_CARD_RE = re.compile(
    r"\d+\.\d{2}|form\s*:|off\s*time|\|\s*j:|\brunners\s*:", re.IGNORECASE
)


def wants_live_card(text: str) -> bool:
    """True when the message is about race data (or pastes a card)."""
    t = (text or "").lower().strip()
    if not t:
        return False
    if _PASTED_CARD_RE.search(t):
        return True
    return any(w in t for w in _CARD_NOUNS)


class ContextBuilder:
    async def build(self, session_key: str, user_message: str, history: list[dict], intent: str | None) -> str:
        # FAST PATH: trivial/filler messages — skip heavy lookups
        msg = user_message.strip()
        if len(msg) < 40 and _TRIVIAL_PATTERNS.match(msg):
            return f"[QUERY]\n{user_message[:2000]}"

        # Card-intent gate: conversational turns skip the live snapshot +
        # web search entirely. They still get memory + history below.
        card_turn = wants_live_card(msg)

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
            if brain and brain.memory and brain.memory._is_ready and card_turn:
                insights = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(None, brain.memory.search_form_insights, user_message, 3),
                    timeout=3.0,
                )
                if insights:
                    parts.append(f"[FORM INSIGHTS]\n{insights[:2000]}")
        except Exception:
            pass

        if card_turn:
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

        if card_turn:
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
