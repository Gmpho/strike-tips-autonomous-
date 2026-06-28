# Strike Tips Chat Architecture Refactor - SPEC

## Goal
Replace Orchestrator/Pipeline with nanobot-inspired MessageBus + AgentLoop architecture. Fresh implementation, no fallbacks.

## Architecture

```
Telegram ──┐
REST ──────┤
WS ────────┤    MessageBus (asyncio.Queue)
            ▼
      ┌─────────────┐
      │ AgentLoop   │
      │ TurnState:  │
      │ RESTORE → COMPACT → COMMAND → BUILD → RUN → SAVE → RESPOND → DONE
      └──────┬──────┘
             │
       ┌─────┴─────┐
       ▼           ▼
  ContextBuilder  ProviderRouter
  (ChromaDB+      (Groq→Gemini)
   Snapshot+
   Honcho)
```

## File Structure (New Code Only)

```
core_agent/
├── bus/
│   ├── queue.py      # MessageBus
│   └── events.py     # InboundMessage, OutboundMessage, TurnState
├── channels/
│   ├── base.py       # BaseChannel ABC
│   ├── rest_channel.py
│   ├── ws_channel.py
│   ├── telegram_channel.py
│   └── manager.py    # ChannelManager
├── agent/
│   ├── loop.py       # AgentLoop (TurnState machine)
│   ├── runner.py     # AgentRunner (LLM + tools)
│   ├── session.py    # SessionManager
│   ├── context.py    # ContextBuilder
│   └── providers/
│       ├── base.py   # LLMProvider ABC
│       ├── groq.py
│       ├── gemini.py
│       └── router.py
├── api/
│   ├── server.py     # aiohttp app factory
│   ├── openai.py     # /v1/chat/completions
│   └── websocket.py  # /ws/chat
└── routes/
    └── agent.py      # Legacy endpoints delegate to bus
```

## Key Interfaces

### bus/events.py
```python
class InboundMessage:
    session_key: str
    channel: str
    chat_id: str
    content: str
    media: List[Media] | None = None

class OutboundMessage:
    session_key: str
    channel: str
    chat_id: str
    content: str
    delta: bool = False
    done: bool = False
    tool_calls: List[ToolCall] | None = None
    parse_mode: str = "Markdown"

class TurnState(Enum):
    RESTORE = "restore"
    COMPACT = "compact"
    COMMAND = "command"
    BUILD = "build"
    RUN = "run"
    SAVE = "save"
    RESPOND = "respond"
    DONE = "done"
```

### channels/base.py
```python
class BaseChannel(ABC):
    @abstractmethod
    async def start(self) -> None: ...
    @abstractmethod
    async def stop(self) -> None: ...
    @abstractmethod
    async def send(self, msg: OutboundMessage) -> None: ...
```

### bus/queue.py
```python
class MessageBus:
    inbound: asyncio.Queue[InboundMessage]
    outbound: asyncio.Queue[OutboundMessage]
    def __init__(self): ...
    async def publish(self, msg: InboundMessage) -> None: ...
    async def subscribe(self) -> AsyncIterator[OutboundMessage]: ...
```

### agent/loop.py
```python
class AgentLoop:
    def __init__(self, bus, session_mgr, context_builder, tool_registry, provider_router): ...
    async def process(self, msg: InboundMessage) -> None:
        # TurnState: RESTORE→COMPACT→COMMAND→BUILD→RUN→SAVE→RESPOND→DONE
```

## Migration Phases

| Phase | Files | Test |
|-------|-------|------|
| 0 | bus/queue.py, bus/events.py | Unit |
| 1 | channels/base.py, rest_channel.py, manager.py | `/api/agent/health` |
| 2 | agent/providers/base.py, groq.py, gemini.py, router.py | LLM call |
| 3 | agent/tools/registry.py (wrap existing) | Tool call |
| 4 | agent/session.py, context.py | Context build |
| 5 | agent/runner.py, loop.py | Full turn |
| 6 | channels/telegram_channel.py | Telegram bot |
| 7 | channels/ws_channel.py, api/websocket.py | WS test |
| 8 | api/openai.py, api/server.py | `/v1/chat/completions` |
| 9 | routes/agent.py (delegate) | Legacy endpoints |

## Decisions (Fixed)

| Item | Decision |
|------|----------|
| Streaming | WebSocket (not SSE) |
| API | OpenAI-compatible `/v1/chat/completions` |
| Session | `session_key` (nanobot pattern) |
| Bus | In-memory `asyncio.Queue` first |
| Frontend | React + Vite → WebSocket |

## Testing Strategy

1. Unit tests per module
2. Integration: `agent_loop + provider_router + tools`
3. E2E: Telegram → bus → loop → response
4. Frontend: WS connect → send → stream receive

## Constraints

- **No fallbacks** to old Orchestrator/Pipeline
- **No duplicate** code - reuse existing maf_tool_registry, chroma, providers
- **Clean** - max 200 lines per file
- **Type hints** everywhere