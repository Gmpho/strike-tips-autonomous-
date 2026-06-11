from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Session:
    session_key: str
    history: list[dict] = field(default_factory=list)
    final_response: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}

    def get(self, session_key: str) -> Session:
        if session_key not in self._sessions:
            self._sessions[session_key] = Session(session_key=session_key)
        return self._sessions[session_key]

    def delete(self, session_key: str) -> None:
        self._sessions.pop(session_key, None)

    def clear(self) -> None:
        self._sessions.clear()