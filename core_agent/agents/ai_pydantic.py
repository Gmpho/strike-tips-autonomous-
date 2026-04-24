"""
Strike Tips - MAF Agent Pipeline
Replaces hand-rolled httpx pipeline with proper MAF Agent dispatch.
UnifiedOrchestrator.chat() signature is unchanged for backward compat.
"""
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from agent_framework import SkillsProvider

from core_agent.agents.chroma_context import ChromaContextProvider
from core_agent.agents.schemas import AgentReply, IntentResponse
from core_agent.config.model_config import ModelConfig
from core_agent.config.model_factory import get_client, get_client_chain
from core_agent.skills.race_schedule import list_supported_tracks, resolve_track_request

logger = logging.getLogger("ai-pydantic")

_SKILLS_DIR = Path(__file__).parent.parent / "skills"


def build_unsupported_track_response(message: str) -> Optional[str]:
    """Return deterministic capability response when unsupported geography is requested."""
    resolution = resolve_track_request(message)
    if not resolution or resolution.supported:
        return None
    supported = ", ".join(track.title() for track in list_supported_tracks())
    nearest = "Vaal, Turffontein, Kenilworth"
    return (
        f"I can't scan {resolution.canonical.replace('_', ' ').title()} right now "
        f"(region: {resolution.region}). I currently support South African tracks only: "
        f"{supported}. Nearest supported options to try: {nearest}."
    )

# ── Backward-compat response dataclass ───────────────────────────────────────

@dataclass
class AgentResponse:
    summary: str
    model_used: str = "unknown"
    confidence: float = 0.8
    tool_calls: List[Dict] = field(default_factory=list)
    raw_output: Optional[str] = None
    suggested_action: Optional[str] = None
    token_usage: Optional[Dict] = None  # {input, output, total}

    @property
    def success(self) -> bool:
        return self.confidence > 0.0


# ── Intent keyword classifier (fast path, no LLM) ────────────────────────────

class IntentClassifier:
    PATTERNS = {
        "get_account_summary":        ["balance", "bankroll", "how much", "account", "pnl", "profit", "loss"],
        "run_daily_analysis":         ["tracks", "racing today", "races", "scan", "today", "what's running"],
        "evaluate_race":              ["analyse", "analyze", "evaluate", "assess race", "pick", "who will win", "predict"],
        "record_selection":           ["record", "place", "select", "back", "wager"],
        "search_racing_data":         ["search", "find", "lookup", "info", "news"],
        "calculate_probability_edge": ["edge", "probability", "odds math"],
        "calculate_max_position":     ["max stake", "position size", "how much can i"],
        "verify_race_exists":         ["exists", "check race", "valid"],
        "get_odds_snapshot":          ["odds", "prices", "snapshot"],
        "search_past_races":          ["past", "memory", "history", "previous"],
        "update_race_result":         ["settle", "won", "lost", "result"],
    }

    INTENT_SPECIALIST = {
        "evaluate_race": "analyst",
        "search_past_races": "analyst",
        "search_racing_data": "search",
        "calculate_probability_edge": "analyst",
        "run_daily_analysis": "scanner",
        "verify_race_exists": "scanner",
        "get_odds_snapshot": "scanner",
        "get_account_summary": "bankroll",
        "calculate_max_position": "bankroll",
        "record_selection": "bankroll",
        "update_race_result": "bankroll",
    }

    def classify(self, message: str) -> Optional[str]:
        msg = message.lower()
        for intent, keywords in self.PATTERNS.items():
            if any(kw in msg for kw in keywords):
                return intent
        return None

    def specialist_for(self, intent: str) -> str:
        return self.INTENT_SPECIALIST.get(intent, "analyst")


# ── Model Pipeline ────────────────────────────────────────────────────────────

class ModelPipeline:
    """
    MAF-backed pipeline. Replaces raw httpx calls with proper Agent dispatch.
    Fallback chain: local Ollama → Groq → Gemini.
    """

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.classifier = IntentClassifier()
        self._session = None

        # Build shared providers
        self._skills = SkillsProvider(skill_paths=_SKILLS_DIR)
        self._chroma = ChromaContextProvider(
            getattr(strike_tips, "memory", None)
        ) if strike_tips else None

        # Agents built lazily on first use
        self._agents: Dict[str, Any] = {}

    def _get_agent(self, name: str):
        """Build agent on first use — avoids loading all model clients at startup."""
        if name not in self._agents and self.strike:
            self._build_agent(name)
        return self._agents.get(name)

    def _build_agent(self, name: str):
        from core_agent.agents.specialists.analyst_agent import build_analyst_agent
        from core_agent.agents.specialists.bankroll_agent import build_bankroll_agent
        from core_agent.agents.specialists.scanner_agent import build_scanner_agent
        from core_agent.agents.specialists.search_agent import build_search_agent
        builders = {
            "analyst":  lambda: build_analyst_agent(self.strike, self._skills, self._chroma),
            "bankroll": lambda: build_bankroll_agent(self.strike, self._skills),
            "scanner":  lambda: build_scanner_agent(self.strike, self._skills, self._chroma),
            "search":   lambda: build_search_agent(self.strike, self._skills),
        }
        if name in builders:
            try:
                self._agents[name] = builders[name]()
            except Exception as e:
                logger.warning(f"[MAF] Failed to build {name} agent: {e}")

    async def _run_with_fallback(self, specialist: str, message: str) -> AgentReply:
        """Run specialist agent; fall back to Groq then Gemini on failure."""
        import time
        from core_agent.core.performance_tracker import tracker

        agent = self._get_agent(specialist) or self._get_agent("analyst")

        def _extract_usage(result) -> Optional[dict]:
            ud = getattr(result, "usage_details", None)
            if not ud:
                return None
            return {
                "input": ud.get("input_token_count"),
                "output": ud.get("output_token_count"),
                "total": ud.get("total_token_count"),
            }

        # Try local agent first when available
        if agent is not None:
            t0 = time.time()
            try:
                result = await agent.run(message, session=agent.create_session())
                latency = time.time() - t0
                text = result.text if hasattr(result, "text") else str(result)
                usage = _extract_usage(result)
                tracker.track_request(specialist, latency=latency, cost=0.0, success=True)
                return AgentReply(summary=text, model_used=specialist, token_usage=usage)
            except Exception as e:
                logger.warning(f"[MAF] Local {specialist} failed: {e}")
        else:
            logger.warning(f"[MAF] No local agent available for specialist={specialist}")

        # Groq fallback
        if ModelConfig.groq_available():
            try:
                groq_client = get_client("ORCHESTRATOR")
                fallback = groq_client.as_agent(
                    name=f"{specialist}_groq",
                    instructions=agent._instructions if agent and hasattr(agent, "_instructions") else "",
                    tools=getattr(agent, "_tools", []),
                    context_providers=[self._skills],
                )
                t0 = time.time()
                result = await fallback.run(message, session=fallback.create_session())
                latency = time.time() - t0
                text = result.text if hasattr(result, "text") else str(result)
                usage = _extract_usage(result)
                tracker.track_request("groq", latency=latency, cost=0.0, success=True)
                from core_agent.config.model_config import ModelConfig as MC
                return AgentReply(summary=text, model_used=f"groq:{MC.ORCHESTRATOR}", token_usage=usage)
            except Exception as e:
                logger.warning(f"[MAF] Groq fallback failed: {e}")

        # Gemini chain fallback
        for gemini_model in ModelConfig.GEMINI_CHAIN:
            try:
                from agent_framework.openai import OpenAIChatClient
                import os
                gem_client = OpenAIChatClient(
                    model_id=gemini_model,
                    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                    api_key=os.getenv("GEMINI_API_KEY", ""),
                )
                fallback = gem_client.as_agent(
                    name=f"{specialist}_gemini",
                    instructions="You are Strike Tips Racing AI. Answer concisely.",
                )
                t0 = time.time()
                result = await fallback.run(message, session=fallback.create_session())
                latency = time.time() - t0
                text = result.text if hasattr(result, "text") else str(result)
                usage = _extract_usage(result)
                tracker.track_request(f"gemini:{gemini_model}", latency=latency, cost=0.0, success=True)
                return AgentReply(summary=text, model_used=f"gemini:{gemini_model}", token_usage=usage)
            except Exception as e:
                logger.warning(f"[MAF] Gemini {gemini_model} failed: {e}")

        return AgentReply(
            summary="All models unavailable. Please try again in 30 seconds.",
            model_used="unavailable",
        )

    async def chat(self, message: str, model_override: Optional[str] = None) -> AgentResponse:
        unsupported_response = build_unsupported_track_response(message)
        if unsupported_response:
            return AgentResponse(
                summary=unsupported_response,
                model_used="intent_handler",
                confidence=1.0,
            )

        # 1. Fast keyword classification
        intent = self.classifier.classify(message)
        specialist = self.classifier.specialist_for(intent) if intent else "analyst"

        if model_override:
            specialist = model_override

        # 2. Dispatch to MAF agent with fallback (supports lazy cold-start)
        reply = await self._run_with_fallback(specialist, message)

        return AgentResponse(
            summary=reply.summary,
            model_used=reply.model_used,
            confidence=0.85 if reply.model_used != "unavailable" else 0.0,
            token_usage=reply.token_usage,
        )


# ── Unified Orchestrator (public API — signature unchanged) ───────────────────

class UnifiedOrchestrator:
    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.pipeline = ModelPipeline(strike_tips)
        self._history: List[Dict] = []

    async def chat(self, message: str, model_override: Optional[str] = None) -> AgentResponse:
        msg_lower = message.lower().strip()

        # Instant handlers (no LLM)
        if msg_lower in ("hi", "hello", "hey"):
            return AgentResponse(
                summary="🏇 Strike Tips AI ready. Ask me about race cards, value bets, or your bankroll.",
                model_used="intent_handler", confidence=1.0,
            )
        if any(kw in msg_lower for kw in ("status", "balance", "bankroll", "how much", "my account", "my balance")) and self.strike:
            try:
                s = self.strike.get_bankroll_status()
                return AgentResponse(
                    summary=f"💰 Bankroll: R{s['current_bankroll']:.2f} | P&L: R{s['total_profit_loss']:.2f} | Open: {s['open_bets']}",
                    model_used="intent_handler", confidence=1.0,
                )
            except Exception:
                pass

        response = await self.pipeline.chat(message, model_override=model_override)
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": response.summary})
        self._history = self._history[-20:]
        return response

    def clear_history(self):
        self._history = []


# ── Keep ModelFactory + IntentClassifier importable for any existing imports ──
class ModelFactory:
    MODELS: Dict = {}
    FALLBACK_CHAIN: List[str] = ["racing_llama", "racing_qwen"]

    @classmethod
    def get_all(cls) -> Dict:
        return cls.MODELS
