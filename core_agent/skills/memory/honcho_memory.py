import logging
from typing import Optional

from core_agent.skills.memory.jsonl_session import JSONLSession

logger = logging.getLogger("honcho-memory")


class HonchoMemory:
    def __init__(self, user_id: Optional[str] = None):
        self._user_id = user_id or "anon_web"
        self._session = JSONLSession(user_id=self._user_id)

    def get_context(self, query: Optional[str] = None) -> str:
        try:
            if query:
                results = self._session.keyword_search(query, n=3)
                if results:
                    return "\n".join(r["content"] for r in results)
            recent = self._session.get_history(limit=5)
            if recent:
                return "\n".join(f"{m['role']}: {m['content']}" for m in recent)
        except Exception as e:
            logger.debug("get_context failed: %s", e)
        return ""

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        try:
            self._session.add_message("user", user_message)
            self._session.add_message("assistant", assistant_message)
        except Exception as e:
            logger.debug("add_turn failed: %s", e)


class DreamHoncho:
    """Dream memory placeholder — two-phase memory writes MEMORY.md files instead."""

    def get_dream_context(self) -> str:
        return ""


dream_honcho = DreamHoncho()
