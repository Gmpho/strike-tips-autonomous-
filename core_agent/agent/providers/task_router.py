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

CLOUD_TIMEOUT = 12.0  # Groq handles this easily; prevents premature fallback to local Ollama


class TaskRouter:
    """
    Routes chat requests to the optimal model based on detected intent.
    """

    def __init__(self) -> None:
        self.ollama = OllamaProvider()
        self.cloud_providers = [GroqProvider(), GeminiProvider()]

    def _load_settings(self) -> dict:
        from core_agent.config.paths import DATA_DIR
        import json
        import os
        settings_file = os.path.join(str(DATA_DIR), "settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

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

            # Recent results — filter by any mentioned course dynamically
            if "result" in last_msg:
                if ATR_RESULTS_PATH.exists():
                    fn = TOOL_REGISTRY.get("get_atr_results")
                    if fn:
                        result = await fn() if asyncio.iscoroutinefunction(fn) else fn()
                        all_results = result.get("results", [])
                        # Find any course name mentioned in the query
                        course_filter = None
                        all_courses = {r.get("course", "").lower() for r in all_results}
                        for c in all_courses:
                            if c and c in last_msg:
                                course_filter = c
                                break
                        filtered = [r for r in all_results if course_filter is None or course_filter in r.get("course", "").lower()]
                        if filtered:
                            label = f" {course_filter.title()}" if course_filter else ""
                            lines = [f"**Recent{label} Results:**"]
                            for r in filtered[:10]:
                                lines.append(f"\n{r.get('course', '?')} {r.get('date', '?')} {r.get('time','?')}")
                                lines.append(f"  {r.get('title','').strip()[:80]}")
                                for h in r.get("runners", [])[:3]:
                                    lines.append(f"  • {h.get('name','?')} — {h.get('position','?')} ({h.get('odds','?')})")
                            return "\n".join(lines)
                        return f"No results found{f' for {course_filter.title()}' if course_filter else ''}."

            # Races / odds — match any track dynamically from the live snapshot
            if "odds" in last_msg or "race" in last_msg or "runner" in last_msg or "today" in last_msg:
                try:
                    from core_agent.core.snapshot_cache import get_snapshot
                    snap = get_snapshot()
                    events = snap.get("events", {})
                except Exception:
                    events = {}

                if events:
                    # Build course → events mapping from live snapshot
                    snapshot_courses: dict = {}
                    for eid, ev in events.items():
                        c = (ev.get("course") or ev.get("venue") or "").strip().lower()
                        if c:
                            snapshot_courses.setdefault(c, []).append((eid, ev))

                    # Match any course name from user message
                    track = None
                    for course_name in snapshot_courses:
                        if course_name and course_name in last_msg:
                            track = course_name
                            break

                    if track:
                        track_events = snapshot_courses[track]
                        lines = [f"**Races at {track.title()} today ({len(track_events)} races):**"]
                        for eid, ev in track_events[:10]:
                            runners = ev.get("runners", [])
                            race_name = ev.get("name") or ev.get("en") or "Race"
                            race_time = ev.get("time") or ev.get("start_time") or ""
                            race_num = ev.get("raceNumber", "")
                            lines.append(f"\n**Race {race_num}** — {race_name} ({race_time}) — {len(runners)} runners")
                            for h in runners[:6]:
                                j = h.get("jockeyName", "?")
                                t_name = h.get("trainerName", "?")
                                o = h.get("outcomeName") or h.get("odds") or "?"
                                lines.append(f"  • {h.get('name','?')} | J:{j} T:{t_name} | Odds:{o}")
                            if len(runners) > 6:
                                lines.append(f"  ... and {len(runners)-6} more runners")
                        return "\n".join(lines)

                    elif "today" in last_msg or re.search(r"\brace[s]?\b", last_msg):
                        # Generic "today's races" — list all tracks
                        lines = [f"**Today's Racing — {len(events)} races across {len(snapshot_courses)} tracks:**\n"]
                        for course, course_evs in sorted(snapshot_courses.items()):
                            race_times = [ev.get("time") or ev.get("start_time") or "" for _, ev in course_evs]
                            race_times = [t for t in race_times if t]
                            time_str = (f" ({race_times[0]}–{race_times[-1]})" if len(race_times) > 1
                                        else (f" ({race_times[0]})" if race_times else ""))
                            lines.append(f"• **{course.title()}** — {len(course_evs)} race{'s' if len(course_evs) != 1 else ''}{time_str}")
                        lines.append("\nAsk me about any track e.g. *'races at turffontein'* or *'odds for kempton'*")
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
        model_override: str | None = None,
    ) -> AsyncIterator[str]:
        # Phase 0: Answer from local snapshot data (no model call needed)
        snap = await self._try_snapshot_answer(messages)
        if snap:
            yield snap
            return

        # Load system configuration settings
        settings = self._load_settings()
        local_only = settings.get("localModelOnly", False)
        pref_model = settings.get("preferredModel", "auto")

        # Resolve the active model choice (UI override takes precedence over settings preferredModel)
        active_model = model_override or "auto"
        if active_model == "auto" and pref_model and pref_model != "auto":
            active_model = pref_model

        # Strict Local Override: In local-only mode, AUTO routes directly to the
        # local Ollama model instead of racing cloud providers. Explicit cloud
        # model selections still route to their cloud provider.
        if local_only and active_model == "auto":
            logger.info("[TASK_ROUTER] Strict local mode active. Routing AUTO to local Ollama.")
            try:
                async for chunk in self.ollama.stream(messages, None, intent):
                    yield chunk
                return
            except Exception as e:
                logger.warning("[TASK_ROUTER] Local Ollama unavailable: %s", e)
                yield "Local model is unavailable. Start Ollama or disable Local-Only mode in settings."
                return

        # If a specific model is explicitly requested, route directly to it
        if active_model and active_model != "auto":
            logger.info("[TASK_ROUTER] explicit model override/preference → %s", active_model)
            if active_model in ("groq", "groq-llama", "llama-3.3-70b-versatile", "openai/gpt-oss-120b", "openai/gpt-oss-20b"):
                provider = GroqProvider()
                try:
                    async for chunk in provider.stream(messages, None, intent):
                        yield chunk
                    return
                except Exception as e:
                    logger.warning("[TASK_ROUTER] Groq override failed: %s", e)
            elif active_model in ("gemini", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"):
                provider = GeminiProvider()
                try:
                    async for chunk in provider.stream(messages, None, intent):
                        yield chunk
                    return
                except Exception as e:
                    logger.warning("[TASK_ROUTER] Gemini override failed: %s", e)
            else:
                try:
                    async for chunk in self.ollama.stream(messages, None, intent, model_override=active_model):
                        yield chunk
                    return
                except Exception as e:
                    logger.warning("[TASK_ROUTER] Ollama override %s failed: %s", active_model, e)

        # Auto routing or failed overrides fall through to here:
        # Try cloud providers concurrently ONLY if local_only is disabled
        if not local_only:
            logger.info("[TASK_ROUTER] trying cloud providers")
            cloud_result = await self._try_cloud_concurrent(messages, intent)
            if cloud_result:
                yield cloud_result
                return

        # Fallback notice: cloud is unreachable/disabled and local Ollama is disabled for chat
        logger.info("[TASK_ROUTER] cloud unreachable or local_only is active. Chat fallback disabled.")
        yield "Hi! Cloud services are currently offline or unreachable. " \
              "Please check your internet connection or select a Browser Local (WebGPU) model from the dropdown to run offline chat."
