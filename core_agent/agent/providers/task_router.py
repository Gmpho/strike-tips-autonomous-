"""
TaskRouter — routes requests to specialist local models based on tool intent.

Flow:
  1. Check user message for tool-related keywords
  2. If a tool keyword matches, look up the specialist Ollama model
  3. Route directly to that specialist model (free, local, domain-tuned)
  4. Otherwise fall through to ProviderRouter (Groq → Gemini → Ollama default)

Google AI Edge Gallery pattern: TOOL_INFO[].specialist → taskTypes routing.
"""

from __future__ import annotations
import asyncio
import logging
import re
from collections.abc import AsyncIterator
from typing import Dict, Optional

from core_agent.agent.providers.groq import GroqProvider
from core_agent.agent.providers.gemini import GeminiProvider
from core_agent.agent.providers.ollama import OllamaProvider
from core_agent.tools.maf_tool_registry import TOOL_INFO, TOOL_REGISTRY
from core_agent.config.paths import (
    MARKET_SNAPSHOT_PATH, ATR_RESULTS_PATH, ATR_MOVERS_PATH, ATR_PREDICTOR_PATH,
)

logger = logging.getLogger("task-router")

# ── Build specialist map from TOOL_INFO metadata ──────────────────────────────
SPECIALIST_MAP: Dict[str, str] = {}
for tool_name, info in TOOL_INFO.items():
    specialist = info.get("specialist")
    if specialist:
        SPECIALIST_MAP[tool_name] = specialist

# ── Keywords that suggest a tool-specific request ──────────────────────────────
TOOL_KEYWORDS = {
    "evaluate", "analyse", "analyze", "scan", "search", "find",
    "record", "settle", "stake", "bet", "wager", "edge", "value",
    "account", "balance", "bankroll", "profit", "odds", "tip",
    "predict", "result", "selection", "market", "mover",
    "dream", "insight", "learned",
    "race", "runner", "horse", "jockey", "trainer", "probability",
    "position", "summary", "today", "show", "list", "give", "what",
}


def _build_tool_keyword_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for tool_name in SPECIALIST_MAP:
        parts = tool_name.replace("_", " ").split()
        for part in parts:
            if part not in mapping:
                mapping[part] = tool_name
    mapping["evaluate"] = "evaluate_race"
    mapping["scan"] = "run_daily_analysis"
    mapping["record"] = "record_selection"
    mapping["settle"] = "update_race_result"
    mapping["account"] = "get_account_summary"
    mapping["balance"] = "get_account_summary"
    mapping["edge"] = "calculate_probability_edge"
    mapping["stake"] = "calculate_max_position"
    mapping["search"] = "search_racing_data"
    mapping["odds"] = "get_odds_snapshot"
    mapping["mover"] = "get_atr_market_movers"
    mapping["predict"] = "get_atr_predictor"
    mapping["result"] = "get_atr_results"
    mapping["dream"] = "get_dream_context"
    mapping["insight"] = "save_learned_insight"
    return mapping


KEYWORD_TO_TOOL = _build_tool_keyword_map()

CLOUD_TIMEOUT = 5.0  # Max seconds to wait for cloud providers before fallback


class TaskRouter:
    """
    Routes chat requests to the optimal model based on detected intent.
    """

    def __init__(self) -> None:
        self.ollama = OllamaProvider()
        self.cloud_providers = [GroqProvider(), GeminiProvider()]

    # ── Helpers ────────────────────────────────────────────────────────────────

    def _detect_specialist(self, messages: list[dict], intent: str | None) -> Optional[str]:
        if intent and intent in SPECIALIST_MAP:
            logger.info("[TASK_ROUTER] explicit intent=%s → specialist=%s", intent, SPECIALIST_MAP[intent])
            return SPECIALIST_MAP[intent]

        msg_lower = self._extract_user_query(messages)
        for keyword, tool_name in KEYWORD_TO_TOOL.items():
            if re.search(rf'\b{re.escape(keyword)}[a-z]*', msg_lower):
                specialist = SPECIALIST_MAP.get(tool_name)
                if specialist:
                    logger.info("[TASK_ROUTER] keyword='%s' → tool='%s' → specialist='%s'", keyword, tool_name, specialist)
                    return specialist
        return None

    def _needs_tools(self, messages: list[dict], intent: str | None) -> bool:
        if intent:
            return True
        msg_lower = self._extract_user_query(messages)
        return any(re.search(rf'\b{re.escape(kw)}[a-z]*', msg_lower) for kw in TOOL_KEYWORDS)

    async def _try_cloud_concurrent(self, messages: list[dict], intent: str | None) -> str | None:
        """Try all cloud providers concurrently with a timeout. Returns first complete response or None."""
        async def _collect(provider):
            try:
                chunks = []
                async for chunk in provider.stream(messages, None, intent):
                    chunks.append(chunk)
                return "".join(chunks) if chunks else None
            except Exception as e:
                logger.debug("[TASK_ROUTER] %s failed: %s", type(provider).__name__, e)
                return None

        tasks = [asyncio.create_task(_collect(p)) for p in self.cloud_providers]
        done, pending = await asyncio.wait(tasks, timeout=CLOUD_TIMEOUT, return_when=asyncio.FIRST_COMPLETED)

        for t in pending:
            t.cancel()

        for task in done:
            try:
                result = task.result()
                if result:
                    return result
            except Exception:
                pass
        return None

    # ── Snapshot answer (no model needed) ─────────────────────────────────────

    @staticmethod
    def _extract_user_query(messages: list[dict]) -> str:
        raw = messages[-1]["content"].lower() if messages else ""
        idx = raw.rfind("[query]")
        if idx != -1:
            after = raw[idx + len("[query]"):].strip()
            return after
        return raw

    async def _try_snapshot_answer(self, messages: list[dict]) -> str | None:
        """Answer data-retrieval queries directly from local JSON snapshots."""
        last_msg = self._extract_user_query(messages)

        try:
            import json

            # Market movers
            if "market mover" in last_msg or "odds movement" in last_msg:
                if ATR_MOVERS_PATH.exists():
                    fn = TOOL_REGISTRY.get("get_atr_market_movers")
                    if fn:
                        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
                        movers = result.get("movers", [])
                        if movers:
                            lines = ["**Market Movers for Today:**"]
                            for m in movers[:15]:
                                lines.append(f"- {m.get('horse','?')} at {m.get('course','?')} {m.get('time','?')} — {m.get('current_odds','?')} (from {m.get('first_show','?')}, {m.get('movement','?')} move)")
                            return "\n".join(lines)
                        return "No market movers found in today's data."

            # ATR Predictions
            if "predictor" in last_msg or "predict" in last_msg:
                if ATR_PREDICTOR_PATH.exists():
                    fn = TOOL_REGISTRY.get("get_atr_predictor")
                    if fn:
                        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
                        predictions = result.get("predictions", [])
                        if predictions:
                            lines = ["**ATR Predictor Tips for Today:**"]
                            for p in predictions[:10]:
                                lines.append(f"- {p.get('horse','?')}: {p.get('prediction','?')}")
                            return "\n".join(lines)
                        return "No ATR predictor data available."

            # Recent results
            if "result" in last_msg:
                if ATR_RESULTS_PATH.exists():
                    fn = TOOL_REGISTRY.get("get_atr_results")
                    if fn:
                        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
                        results = result.get("results", [])
                        course = "greyville" if "greyville" in last_msg else None
                        if course:
                            results = [r for r in results if course.lower() in r.get("course","").lower()]
                        if results:
                            lines = [f"**Recent{' Greyville' if course else ''} Results:**"]
                            for r in results[:10]:
                                course_str = r.get("course", "?")
                                ts = r.get("date", "?")
                                lines.append(f"\n{course_str} {ts} {r.get('time','?')}")
                                lines.append(f"  {r.get('title','').strip()[:80]}")
                                for h in r.get("runners", [])[:3]:
                                    lines.append(f"  • {h.get('name','?')} — {h.get('position','?')} ({h.get('odds','?')})")
                            return "\n".join(lines)
                        return f"No results found{f' for Greyville' if course else ''}."

            # Odds snapshot
            if "odds" in last_msg or "race" in last_msg:
                track = None
                for t in ["greyville", "bath", "kempton", "southwell", "utoxeter"]:
                    if t in last_msg:
                        track = t
                        break
                if not track:
                    track = "greyville" if re.search(r"\brace\b", last_msg) or "today" in last_msg else None
                if track:
                    fn = TOOL_REGISTRY.get("get_odds_snapshot")
                    if fn:
                        result = await fn(track=track) if asyncio.iscoroutinefunction(fn) else fn(track=track)
                        events = result.get("events", {})
                        if events:
                            lines = [f"**Races at {track.title()}:**"]
                            for eid, ev in list(events.items())[:8]:
                                runners = ev.get("runners", [])
                                lines.append(f"\n{ev.get('name','?')} ({ev.get('time','?')}) — {len(runners)} runners")
                                for h in runners[:5]:
                                    lines.append(f"  • {h.get('name','?')} — W:{h.get('weight','?')} O:{h.get('outcomeName','?')}")
                                if len(runners) > 5:
                                    lines.append(f"  ... and {len(runners)-5} more")
                            return "\n".join(lines)
        except Exception as e:
            logger.debug("[TASK_ROUTER] snapshot answer failed: %s", e)
        return None

    # ── Main route ────────────────────────────────────────────────────────────

    async def stream(
        self,
        messages: list[dict],
        tools: list[dict] | None,
        intent: str | None,
    ) -> AsyncIterator[str]:
        # Phase 0: Answer from local snapshot data (no model call needed)
        snap = await self._try_snapshot_answer(messages)
        if snap:
            yield snap
            return

        specialist = self._detect_specialist(messages, intent)
        if specialist:
            logger.info("[TASK_ROUTER] specialist route → %s", specialist)
            try:
                yielded = False
                async for chunk in self.ollama.stream(messages, None, intent, model_override=specialist):
                    yielded = True
                    yield chunk
                if yielded:
                    return
            except Exception as e:
                logger.warning("[TASK_ROUTER] specialist %s failed: %s", specialist, e)

        needs_tools = self._needs_tools(messages, intent)
        logger.info("[TASK_ROUTER] no specialist, trying cloud (needs_tools=%s)", needs_tools)

        # Phase 1: All cloud providers concurrently with 5s deadline
        cloud_result = await self._try_cloud_concurrent(messages, intent)
        if cloud_result:
            yield cloud_result
            return

        # Phase 2: Cloud failed + tools needed → functiongemma locally
        if needs_tools:
            logger.info("[TASK_ROUTER] cloud failed, trying functiongemma:270m")
            try:
                yielded = False
                async for chunk in self.ollama.stream(messages, None, intent, model_override="functiongemma:270m"):
                    yielded = True
                    yield chunk
                if yielded:
                    return
            except Exception as e:
                logger.warning("[TASK_ROUTER] functiongemma failed: %s", e)

        # Phase 3: General chat with no tools — return fast instead of cold-start
        if not needs_tools:
            logger.info("[TASK_ROUTER] cloud down + general chat → fast cached response")
            yield "Hi! I'm currently in offline mode — my cloud services aren't reachable. " \
                  "Try asking about today's races, odds, your account, or recent results."
            return

        # Phase 4: Tool-oriented fallback — try local specialist models
        for model_name in ["func_gemma:latest", "qwen3.5:0.8b"]:
            logger.info("[TASK_ROUTER] final fallback → %s", model_name)
            try:
                yielded = False
                async for chunk in self.ollama.stream(messages, None, intent, model_override=model_name):
                    yielded = True
                    yield chunk
                if yielded:
                    return
            except Exception as e:
                logger.warning("[TASK_ROUTER] %s failed: %s", model_name, e)
