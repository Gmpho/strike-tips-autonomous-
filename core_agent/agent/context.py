from __future__ import annotations
import asyncio
import json
from core_agent.core.strike_brain import brain


MAX_CONTEXT_CHARS = 12000


class ContextBuilder:
    async def build(self, session_key: str, user_message: str, history: list[dict], intent: str | None) -> str:
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
            from core_agent.core.snapshot_cache import get_snapshot
            snap = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(None, get_snapshot),
                timeout=3.0,
            )
            if snap and snap.get("events"):
                summary = self._truncate_snapshot(snap)
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

    def _truncate_snapshot(self, snap: dict) -> str | None:
        events = snap.get("events", {})
        if not events:
            return None
        lines = [f"Today's races ({len(events)} events):"]
        for eid, ev in list(events.items())[:8]:
            name = ev.get("en", "?")
            venue = ev.get("venue_name", ev.get("venue", ""))
            time = ev.get("start_time", ev.get("time", ""))
            lines.append(f"  #{eid}: {name} @ {venue} {time}")
        return "\n".join(lines)
