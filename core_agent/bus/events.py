from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Optional
import uuid


class TurnState(str, Enum):
    RESTORE = "restore"
    COMPACT = "compact"
    COMMAND = "command"
    BUILD = "build"
    RUN = "run"
    SAVE = "save"
    RESPOND = "respond"
    DONE = "done"


@dataclass
class ToolCall:
    name: str
    args: dict
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class Media:
    type: str
    data: bytes | str
    mime_type: str | None = None


@dataclass
class InboundMessage:
    session_key: str
    channel: str
    chat_id: str
    content: str
    media: List[Media] = field(default_factory=list)
    session_key_override: str | None = None
    user_id: int | None = None


@dataclass
class OutboundMessage:
    session_key: str
    channel: str
    chat_id: str
    content: str
    delta: bool = False
    done: bool = False
    tool_calls: List[ToolCall] = field(default_factory=list)
    parse_mode: str = "Markdown"