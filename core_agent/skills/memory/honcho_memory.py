import logging
from datetime import datetime
from typing import Optional

from core_agent.skills.memory.chroma_memory import RacingMemory

logger = logging.getLogger("honcho-memory")


class HonchoMemory:
    def __init__(self, user_id: Optional[str] = None):
        self._user_id = user_id or "anon_web"
        self._memory = RacingMemory()

    def get_context(self, query: Optional[str] = None) -> str:
        try:
            if query:
                results = self._memory.search_form_insights(query, n_results=3)
                if results:
                    lines = [r["content"] for r in results]
                    return "\n".join(lines)
            recent = self._memory.get_chat_history(limit=5)
            if recent:
                parts = [f"{m['role']}: {m['content']}" for m in recent]
                return "\n".join(parts)
        except Exception as e:
            logger.debug(f"get_context failed: {e}")
        return ""

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        try:
            self._memory.add_chat_message("user", user_message, source=f"user_{self._user_id}")
            self._memory.add_chat_message("assistant", assistant_message, source="agent")
        except Exception as e:
            logger.debug(f"add_turn failed: {e}")


class DreamHoncho:
    def get_dream_context(self) -> str:
        return ""


dream_honcho = DreamHoncho()
