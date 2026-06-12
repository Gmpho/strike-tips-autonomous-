from __future__ import annotations
from core_agent.bus.queue import MessageBus
from core_agent.bus.events import InboundMessage, OutboundMessage, TurnState
from core_agent.agent.session import SessionManager
from core_agent.agent.context import ContextBuilder
from core_agent.agent.runner import AgentRunner
from core_agent.agent.providers.task_router import TaskRouter
from core_agent.core.strike_brain import brain


class AgentLoop:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus
        self.session_mgr = SessionManager()
        self.context_builder = ContextBuilder()
        self.runner = AgentRunner(TaskRouter())

    async def process(self, msg: InboundMessage) -> None:
        session = self.session_mgr.get(msg.session_key)
        state = TurnState.RESTORE

        while state != TurnState.DONE:
            if state == TurnState.RESTORE:
                state = TurnState.COMPACT

            elif state == TurnState.COMPACT:
                state = TurnState.COMMAND

            elif state == TurnState.COMMAND:
                if self._is_command(msg.content):
                    await self._handle_command(msg, session)
                    state = TurnState.DONE
                else:
                    state = TurnState.BUILD

            elif state == TurnState.BUILD:
                context = await self.context_builder.build(
                    msg.session_key, msg.content, session.history, None
                )
                messages = [
                    {"role": "system", "content": "You are Strike Tips AI, expert in horse racing analysis."},
                    *session.history,
                    {"role": "user", "content": context},
                ]
                session.messages = messages
                state = TurnState.RUN

            elif state == TurnState.RUN:
                full_response = ""
                async for chunk in self.runner.run_stream(session.messages, None):
                    full_response += chunk
                    await self.bus.publish_outbound(OutboundMessage(
                        session_key=msg.session_key,
                        channel=msg.channel,
                        chat_id=msg.chat_id,
                        content=chunk,
                        delta=True,
                    ))
                session.final_response = full_response
                session.history.append({"role": "user", "content": msg.content})
                session.history.append({"role": "assistant", "content": full_response})
                session.history = session.history[-20:]
                state = TurnState.SAVE

            elif state == TurnState.SAVE:
                try:
                    if brain and brain.memory and brain.memory._is_ready:
                        brain.memory.add_chat_message("user", msg.content, source=f"user_{msg.session_key}")
                        brain.memory.add_chat_message("assistant", session.final_response, source="agent_strike")
                except Exception:
                    pass
                state = TurnState.RESPOND

            elif state == TurnState.RESPOND:
                await self.bus.publish_outbound(OutboundMessage(
                    session_key=msg.session_key,
                    channel=msg.channel,
                    chat_id=msg.chat_id,
                    content=session.final_response,
                    done=True,
                ))
                state = TurnState.DONE

    def _is_command(self, text: str) -> bool:
        return text.strip().startswith("/")
