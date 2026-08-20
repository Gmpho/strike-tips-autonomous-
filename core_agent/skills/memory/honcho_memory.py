"""
HonchoMemory — dual-layer memory for Strike Tips agents.

Layer 1 (fast): JSONLSession — local per-user JSONL file.
  - Instant reads/writes, no network, recent conversation context.

Layer 2 (deep): Honcho cloud — api.honcho.dev
  - Background reasoning builds synthesised user representations across sessions.
  - "This user prefers Kenilworth, avoids long-shots, bets on Saturdays."
  - Only called if HONCHO_API_KEY is set.

Both layers inject into the LLM prompt. JSONL is always primary.
Honcho is best-effort — if it fails/is slow, the agent still works fine.
"""

import logging
import os
import typing as _typing
from datetime import date
from typing import Optional

from typing_extensions import Self as _Self
_typing.Self = _Self

from core_agent.skills.memory.jsonl_session import JSONLSession

logger = logging.getLogger("honcho-memory")

WORKSPACE_ID = os.getenv("HONCHO_WORKSPACE_ID", "strike-tips-prod")


def _make_honcho_client():
    """Return a Honcho client if API key is configured, else None."""
    api_key = os.getenv("HONCHO_API_KEY", "")
    if not api_key or api_key == "your_honcho_api_key_here":
        return None
    try:
        from honcho import Honcho
        return Honcho(workspace_id=WORKSPACE_ID, api_key=api_key, environment="production")
    except Exception as e:
        logger.warning(f"[honcho] client init failed: {e}")
        return None


class HonchoMemory:
    """
    Dual-layer memory per user.
    user_id = Telegram chat_id (str) for real users, "anon_web" for HUD.
    """

    def __init__(self, user_id: Optional[str] = None):
        self._user_id = str(user_id) if user_id else "anon_web"
        # Layer 1: local JSONL (always available)
        self._session = JSONLSession(user_id=self._user_id)
        # Layer 2: Honcho cloud (lazy, optional)
        self._honcho = None
        self._user_peer = None
        self._agent_peer = None

    def _ensure_honcho(self) -> bool:
        if self._honcho is not None:
            return True
        client = _make_honcho_client()
        if not client:
            return False
        try:
            self._honcho = client
            self._user_peer = client.peer(f"user_{self._user_id}")
            self._agent_peer = client.peer("agent_strike")
            return True
        except Exception as e:
            logger.warning(f"[honcho] peer init failed: {e}")
            return False

    def _honcho_session_id(self) -> str:
        return f"{self._user_id}_{date.today().isoformat()}"

    def get_context(self, query: Optional[str] = None) -> str:
        """
        Build prompt context from both layers.
        Returns combined string ready for LLM injection.
        """
        parts = []

        # Layer 1: recent JSONL history (always fast)
        try:
            if query:
                recent = self._session.keyword_search(query, n=3)
            else:
                recent = self._session.get_history(limit=5)
            if recent:
                history_str = "\n".join(f"{m['role']}: {m['content']}" for m in recent)
                parts.append(f"[RECENT HISTORY]\n{history_str}")
        except Exception as e:
            logger.debug(f"JSONL context failed: {e}")

        # Layer 2: Honcho deep reasoning (best-effort, ~200ms)
        if self._ensure_honcho():
            try:
                insight = self._user_peer.chat(
                    "Summarise this bettor's preferences, favourite tracks, risk tolerance and patterns in 2 sentences max."
                )
                if insight:
                    parts.append(f"[USER PROFILE]\n{insight}")
            except Exception as e:
                logger.debug(f"Honcho context failed: {e}")

        return "\n\n".join(parts)

    def add_turn(self, user_message: str, assistant_message: str) -> None:
        """Write to both layers. JSONL is synchronous; Honcho is best-effort."""
        # Layer 0: curated memory files (agent_notes.md / user_prefs.md)
        try:
            from core_agent.skills.memory.curated_memory import curated_memory
            cu = (user_message or "").strip().lower()
            CURATED_MARKERS = ("i prefer", "i like", "prefer ", "favourite track", "favorite track",
                               "don't bet", "never bet", "always bet", "risk", "bankroll", "stake",
                               "bet saturday", "bet on", "avoid", "my style", "i want", "please ")
            if cu and any(m in cu for m in CURATED_MARKERS):
                curated_memory.append_user_pref(user_message.strip()[:280])
            # Log a lightweight agent note when new betting patterns are seen each day
            note = f"Conversation turn processed (user={self._user_id}, msgs={len(user_message or '')}+{len(assistant_message or '')})"
            curated_memory.append_agent_note(note[:200])
        except Exception as e:
            logger.debug(f"Curated memory write failed: {e}")

        # Layer 1: always write locally
        try:
            self._session.add_message("user", user_message)
            self._session.add_message("assistant", assistant_message)
        except Exception as e:
            logger.debug(f"JSONL write failed: {e}")

        # Layer 2: write to Honcho for background reasoning
        if self._ensure_honcho():
            try:
                session = self._honcho.session(self._honcho_session_id())
                session.add_peers([self._user_peer, self._agent_peer])
                session.add_messages([
                    self._user_peer.message(user_message),
                    self._agent_peer.message(assistant_message),
                ])
            except Exception as e:
                logger.debug(f"Honcho write failed: {e}")

    def ping(self) -> dict:
        honcho_ok = self._ensure_honcho()
        return {
            "jsonl": str(self._session._path),
            "honcho": "connected" if honcho_ok else "not_configured",
        }


class DreamHonchoMemory:
    """Dream agent peer — writes simulation insights to Honcho for agent_strike to query."""

    def __init__(self):
        self._honcho = None
        self._dream_peer = None

    def _ensure(self) -> bool:
        if self._honcho is not None:
            return True
        client = _make_honcho_client()
        if not client:
            return False
        try:
            self._honcho = client
            self._dream_peer = client.peer("agent_dream")
            return True
        except Exception as e:
            logger.warning(f"[honcho-dream] init failed: {e}")
            return False

    def record_dream(self, scenario: str, insight: str, track: str) -> None:
        if not self._ensure():
            return
        try:
            session = self._honcho.session(f"dreams_{date.today().isoformat()}")
            session.add_peers([self._dream_peer])
            session.add_messages([
                self._dream_peer.message(
                    f"[DREAM] Track:{track} | Scenario:{scenario} | Insight:{insight}"
                )
            ])
        except Exception as e:
            logger.debug(f"[honcho-dream] record failed: {e}")

    def get_dream_context(self) -> str:
        if not self._ensure():
            # Fall back to local dream memory markdown
            try:
                from core_agent.core.dream_memory import read_memories
                dreams = read_memories("dreams", limit=3)
                if dreams:
                    return " | ".join(d.get("body", "") for d in dreams if d.get("body"))
            except Exception:
                pass
            return ""
        try:
            return self._dream_peer.chat(
                "What race scenarios has this agent been simulating? 2 sentences max."
            ) or ""
        except Exception as e:
            logger.debug(f"[honcho-dream] context failed: {e}")
            return ""


# Module-level singletons
dream_honcho = DreamHonchoMemory()
