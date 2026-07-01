from __future__ import annotations
import asyncio
import logging
from core_agent.bus.queue import MessageBus
from core_agent.bus.events import InboundMessage, OutboundMessage, TurnState
from core_agent.agent.session import SessionManager, Session
from core_agent.agent.context import ContextBuilder
from core_agent.agent.runner import AgentRunner
from core_agent.agent.providers.task_router import TaskRouter
from core_agent.agent.prompts import build_system_prompt
from core_agent.core.strike_brain import brain

logger = logging.getLogger("agent-loop")


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
                    {"role": "system", "content": build_system_prompt()},
                    *session.history,
                    {"role": "user", "content": context},
                ]
                session.messages = messages
                state = TurnState.RUN

            elif state == TurnState.RUN:
                full_response = ""
                model_override = getattr(msg, "model", None)
                if not model_override or model_override == "auto":
                    model_override = session.metadata.get("preferred_model")
                async for chunk in self.runner.run_stream(session.messages, None, model_override=model_override):
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

    async def _handle_command(self, msg: InboundMessage, session: Session) -> None:
        cmd_text = msg.content.strip()
        parts = cmd_text.split()
        cmd = parts[0].lower()
        args = parts[1:]

        response_content = ""

        if cmd == "/start" or cmd == "/help":
            response_content = (
                "🏇 *Strike Tips Agent*\n\n"
                "I'm your AI Racing Data Analyst. Just chat with me or use commands:\n\n"
                "• `/model <name>` — Switch active model for this chat session\n"
                "• `/model` — Show current selected model & all options\n"
                "• `/status` — Quick account & bankroll summary\n"
                "• `/scan` — Start today's full racing scan\n"
                "• `/clear` — Reset conversation history\n"
                "• `/help` — Show this help menu"
            )

        elif cmd == "/clear":
            session.history.clear()
            response_content = "🧹 Chat history cleared for this session."

        elif cmd == "/model":
            current_model = session.metadata.get("preferred_model") or "auto"
            
            if not args:
                response_content = (
                    "🧠 *Select active model*\n"
                    "To switch model, reply with `/model <name>`:\n\n"
                    "• `/model auto` — ⚡ Auto Router (optimal)\n"
                    "• `/model groq` — ☁️ Groq Llama 70B\n"
                    "• `/model gemini` — ☁️ Gemini Flash\n"
                    "• `/model racing_qwen` — 🤖 Racing Qwen\n"
                    "• `/model lfm_racing` — 🤖 LFM Racing (Thinking)\n"
                    "• `/model ds_racing` — 🤖 DS Racing (DeepSeek R1)\n"
                    "• `/model qwen3.5` — 🤖 Qwen3.5 0.8B\n"
                    "• `/model functiongemma` — 🤖 FunctionGemma 270M\n\n"
                    f"Current selection: *{current_model}*"
                )
            else:
                choice = args[0].lower()
                mapping = {
                    "auto": "auto",
                    "groq": "groq",
                    "gemini": "gemini",
                    "racing_qwen": "racing_qwen:latest",
                    "racing-qwen": "racing_qwen:latest",
                    "lfm_racing": "lfm_racing:latest",
                    "lfm-racing": "lfm_racing:latest",
                    "lfm": "lfm_racing:latest",
                    "ds_racing": "ds_racing:latest",
                    "ds-racing": "ds_racing:latest",
                    "ds": "ds_racing:latest",
                    "deepseek": "ds_racing:latest",
                    "qwen3.5": "qwen3.5:0.8b",
                    "qwen": "qwen3.5:0.8b",
                    "functiongemma": "functiongemma:270m",
                    "gemma": "functiongemma:270m"
                }
                
                mapped = mapping.get(choice)
                if mapped:
                    session.metadata["preferred_model"] = mapped
                    response_content = f"✅ Active model switched to *{mapped}*. Subsequent requests in this session will use this model."
                else:
                    response_content = f"❌ Unknown model: *{choice}*. Type `/model` to see the list of valid models."

        elif cmd == "/status":
            if not brain.strike:
                response_content = "❌ System not initialized."
            else:
                try:
                    s = brain.strike.get_bankroll_status()
                    response_content = (
                        f"💰 *Account Summary*\n\n"
                        f"• Balance: *R{s.get('current_bankroll', 0.0):.2f}*\n"
                        f"• P&L: *R{s.get('total_profit_loss', 0.0):.2f}*\n"
                        f"• Open Bets: *{s.get('open_bets', 0)}*\n"
                        f"• Drawdown: *{s.get('drawdown_percent', 0.0):.1f}%*"
                    )
                except Exception as e:
                    response_content = f"❌ Error retrieving status: {e}"

        elif cmd == "/scan":
            if not brain.strike:
                response_content = "❌ System not initialized."
            else:
                async def _run_scan_bg():
                    try:
                        await brain.strike.run_daily_scan()
                    except Exception as e:
                        logger.error("Scan command error: %s", e)
                
                asyncio.create_task(_run_scan_bg())
                response_content = "🚀 Starting today's full racing scan in background..."

        elif cmd == "/dream":
            import re
            match = re.match(r"^/dream\s+(\w+)\s+(?:race\s+)?(\d+)\s*-\s*(.+)$", cmd_text, re.IGNORECASE)
            if not match:
                response_content = (
                    "❌ *Invalid Dream Command Format.*\n\n"
                    "• *Usage*: `/dream <track> race <number> - <scenario>`\n"
                    "• *Example*: `/dream greyville race 5 - heavy rain`"
                )
            else:
                track = match.group(1).lower()
                race_num = int(match.group(2))
                scenario = match.group(3).strip()
                
                try:
                    from core_agent.skills.dreamer import dream_engine
                    response_content = (
                        f"🔮 *Simulating race scenario in background...*\n"
                        f"• Track: *{track.title()}*\n"
                        f"• Race: *{race_num}*\n"
                        f"• Scenario: *{scenario}*"
                    )
                    
                    async def _run_dream_bg():
                        try:
                            d = await dream_engine.generate_custom_dream(
                                track=track,
                                race_num=race_num,
                                scenario_override=scenario
                            )
                            await self.bus.publish_outbound(OutboundMessage(
                                session_key=msg.session_key,
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=(
                                    f"✨ *Dream Simulation Complete!*\n\n"
                                    f"🏁 *Track*: {d.track} R{d.race}\n"
                                    f"🎭 *Scenario*: {d.scenario}\n"
                                    f"📊 *Estimated Probability Shift*: `{d.probability_shift * 100:+.1f}%`\n"
                                    f"🧠 *Vividness/Confidence*: `{d.vividness * 100:.1f}%`\n\n"
                                    f"💡 *Insight*: {d.insight}"
                                ),
                                done=True,
                            ))
                        except Exception as e:
                            logger.error("Custom dream error: %s", e)
                            await self.bus.publish_outbound(OutboundMessage(
                                session_key=msg.session_key,
                                channel=msg.channel,
                                chat_id=msg.chat_id,
                                content=f"❌ *Dream simulation failed*: {e}",
                                done=True,
                            ))
                    
                    asyncio.create_task(_run_dream_bg())
                except Exception as e:
                    response_content = f"❌ Error initializing dream: {e}"

        else:
            response_content = f"❓ Unknown command: *{cmd}*. Type `/help` to see list of valid commands."

        await self.bus.publish_outbound(OutboundMessage(
            session_key=msg.session_key,
            channel=msg.channel,
            chat_id=msg.chat_id,
            content=response_content,
            done=True,
        ))
