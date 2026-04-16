"""
Strike Tips - Unified Orchestrator & Model Pipeline (AI Agent Layer)
ModelPipeline: Intent routing → Specialist LLM execution → Synthesized response
UnifiedOrchestrator: High-level chat interface with tool-calling and memory.

Specialist model routing:
  racing_qwen  → Fast reads (race cards, odds, status)
  func_gemma   → Write ops (record_selection, update_race_result)
  lfm_racing   → Deep analysis (evaluate_race, run_daily_analysis)
  racing_llama → Router / fallback
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ai-pydantic")
from core_agent.config.model_config import ModelConfig


# ─── Response Dataclass ───────────────────────────────────────────────────────

@dataclass
class AgentResponse:
    """Standardised agent response object"""
    summary: str
    model_used: str = "unknown"
    confidence: float = 0.8
    tool_calls: List[Dict] = field(default_factory=list)
    raw_output: Optional[str] = None
    suggested_action: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.confidence > 0.0


# ─── Model Factory ────────────────────────────────────────────────────────────

class ModelFactory:
    """
    Registry of all available LLM models with their endpoints and roles.
    Provides a priority chain: local Ollama → cloud Groq fallback.
    """

    MODELS = {
        "racing_llama": {
            "type": "ollama",
            "model": "racing_llama",
            "endpoint": ModelConfig.OLLAMA_HOST,
            "role": "router",
        },
        "racing_qwen": {
            "type": "ollama",
            "model": "racing_qwen",
            "endpoint": ModelConfig.OLLAMA_HOST,
            "role": "fast_reads",
        },
        "func_gemma": {
            "type": "ollama",
            "model": "func_gemma",
            "endpoint": ModelConfig.OLLAMA_HOST,
            "role": "write_ops",
        },
        "lfm_racing": {
            "type": "ollama",
            "model": "lfm_racing",
            "endpoint": ModelConfig.OLLAMA_HOST,
            "role": "deep_analysis",
        },
        # Local models
        "local:llama3.2:1b": {
            "type": "ollama",
            "model": "llama3.2:1b",
            "endpoint": ModelConfig.OLLAMA_HOST,
            "role": "cloud_fallback",
        },
    }

    FALLBACK_CHAIN = [
        "racing_llama",
        "racing_qwen",
        "local:llama3.2:1b",
    ]

    @classmethod
    def get_all(cls) -> Dict:
        return cls.MODELS

    @classmethod
    def get_model_for_role(cls, role: str) -> Optional[str]:
        for name, info in cls.MODELS.items():
            if info["role"] == role:
                return name
        return None


# ─── Intent Classifier ────────────────────────────────────────────────────────

class IntentClassifier:
    """
    Fast Python-based intent classifier — no LLM overhead (~0ms).
    Routes user messages to the right specialist model and tool.
    """

    PATTERNS = {
        "get_account_summary":   ["balance", "bankroll", "how much", "account", "pnl", "profit", "loss"],
        "run_daily_analysis":    ["tracks", "racing today", "races", "sa", "scan", "today", "what's running"],
        "evaluate_race":         ["analyse", "analyze", "evaluate", "assess race", "pick", "who will win", "predict"],
        "record_selection":      ["bet", "place", "select", "back", "wager"],
        "search_racing_data":    ["search", "find", "lookup", "info", "news"],
        "calculate_probability_edge": ["edge", "probability", "odds math", "math"],
        "calculate_max_position": ["stake", "position", "max", "how much can i bet"],
        "verify_race_exists":    ["exists", "check race", "valid"],
        "get_odds_snapshot":     ["odds", "prices", "snapshot"],
        "search_past_races":     ["past", "memory", "history", "previous"],
        "update_race_result":    ["settle", "won", "lost", "result"],
    }

    def classify(self, message: str) -> Optional[str]:
        """Return the best matching intent or None"""
        msg_lower = message.lower()
        for intent, keywords in self.PATTERNS.items():
            if any(kw in msg_lower for kw in keywords):
                return intent
        return None

    def extract_params(self, intent: str, message: str) -> Dict[str, Any]:
        """Extract track and race_number using regex"""
        params = {}
        message_lower = message.lower()
        
        # Track detection
        tracks = ["turffontein", "vaal", "fairview", "scottsville", "kenilworth", "greyville", "durbanville"]
        for t in tracks:
            if t in message_lower:
                params["track"] = t
                break
        
        # Race number detection (Race 1, R1, #1)
        race_match = re.search(r"(?:race|r|#)\s*(\d+)", message_lower)
        if race_match:
            params["race_number"] = int(race_match.group(1))
            
        return params

    def get_specialist(self, intent: str) -> str:
        """Map intent to the best specialist model"""
        INTENT_SPECIALIST = {
            "evaluate_race": "lfm_racing",
            "run_daily_analysis": "lfm_racing",
            "record_selection": "func_gemma",
            "update_race_result": "func_gemma",
            "get_account_summary": "racing_qwen",
            "get_odds_snapshot": "racing_qwen",
            "search_past_races": "racing_qwen",
            "verify_race_exists": "racing_qwen",
            "calculate_probability_edge": "ds_racing",
            "calculate_max_position": "racing_qwen",
            "search_racing_data": "racing_llama",
        }
        return INTENT_SPECIALIST.get(intent, "racing_llama")


# ─── Model Pipeline ───────────────────────────────────────────────────────────

class ModelPipeline:
    """
    Delegation chain: IntentClassifier → Specialist → Synthesizer.
    Uses Python-code tools directly for fast execution (~1-2s).
    Falls back from local Ollama to cloud Groq if local is unavailable.
    """

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.classifier = IntentClassifier()
        self._chat_history: List[Dict] = []

    def _load_system_prompt(self, role: str) -> str:
        """Load specialist system prompt from disk"""
        prompt_map = {
            "evaluate_race": "analyst_agent.txt",
            "run_daily_analysis": "analyst_agent.txt",
            "record_selection": "bankroll_agent.txt",
            "update_race_result": "bankroll_agent.txt",
        }
        prompt_file = prompt_map.get(role, "analyst_agent.txt")
        # Fixed absolute path for Docker container environment
        prompt_path = os.path.join("/app/core_agent/prompts", prompt_file)
        try:
            with open(prompt_path, "r") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to load prompt {prompt_path}: {e}")
            return "You are Strike Tips, an expert South African horse racing analyst."

    async def _call_ollama(
        self, model: str, prompt: str, system: Optional[str] = None
    ) -> Optional[str]:
        """Call local Ollama model with persona-injected system prompt"""
        try:
            import httpx
            from core_agent.config.model_config import ModelConfig
            
            # Use intent-specific system prompt if not provided
            system_prompt = system or self._load_system_prompt(model)
            host = ModelConfig.OLLAMA_HOST or "http://host.docker.internal:11434"
            
            payload = {
                "model": model,
                "prompt": f"{system_prompt}\n\n{prompt}", # Standard prompt format for /generate
                "system": system_prompt,
                "stream": False,
                "options": ModelConfig.ollama_options()
            }
            endpoint = f"{host.rstrip('/')}/api/generate"
            logger.info(f"[OLLAMA] Calling {endpoint} with model {model}")
            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(endpoint, json=payload)
                if resp.status_code == 200:
                    return resp.json().get("response", "")
                else:
                    logger.error(f"[OLLAMA] Error {resp.status_code}: {resp.text}")
        except Exception as e:
            logger.debug(f"Ollama call failed ({model}): {e}")
        return None

    async def _call_groq(self, prompt: str) -> Optional[str]:
        """Call Groq cloud API as fallback"""
        api_key = os.getenv("GROQ_API_KEY", "")
        if not api_key:
            return None
        try:
            import httpx
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 512,
            }
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers=headers, json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
        except Exception as e:
            logger.debug(f"Groq fallback failed: {e}")
        return None

    async def _execute_tool(self, intent: str, message: str) -> Optional[AgentResponse]:
        """Execute a MAF tool directly from intent, returning fast Python response"""
        logger.info(f"[TOOL_DISPATCH] Attempting tool: {intent}")
        try:
            from core_agent.tools.maf_tool_registry import TOOL_REGISTRY
            tool_fn = TOOL_REGISTRY.get(intent)
            if tool_fn and self.strike:
                # Prepare arguments
                tool_args = {"strike": self.strike}
                
                # Automatically extract parameters using the classifier
                extracted_params = self.classifier.extract_params(intent, message)
                tool_args.update(extracted_params)
                
                # Identify if tool expects 'query'
                import inspect
                sig = inspect.signature(tool_fn)
                if 'query' in sig.parameters and 'query' not in tool_args:
                    tool_args['query'] = message
                
                # Handle both async and sync tools
                if asyncio.iscoroutinefunction(tool_fn):
                    result = await tool_fn(**tool_args)
                else:
                    result = tool_fn(**tool_args)
                
                logger.info(f"[TOOL_DISPATCH] Success for {intent}: {result}")
                return AgentResponse(
                    summary=str(result),
                    model_used="tool_direct",
                    confidence=0.99,
                    tool_calls=[{"tool": intent, "result": result}],
                )
            logger.warning(f"[TOOL_DISPATCH] Tool {intent} not found or strike missing.")
        except Exception as e:
            logger.error(f"[TOOL_DISPATCH] Tool execution failed for {intent}: {e}")
            return AgentResponse(
                summary=f"Error executing {intent}: {str(e)}",
                model_used="tool_direct",
                confidence=0.0
            )
        return None

    async def chat(self, message: str, model_override: Optional[str] = None) -> AgentResponse:
        """Main pipeline entry: classify → ground with cache → tool → LLM → response"""
        from datetime import datetime
        import pytz
        import json
        from core_agent.config.paths import MARKET_SNAPSHOT_PATH

        # 1. Prepare Grounding Data
        sa_tz = pytz.timezone('Africa/Johannesburg')
        current_date = datetime.now(sa_tz).strftime('%Y-%m-%d')
        
        grounding_data = f"Current Date: {current_date}\n"
        
        if MARKET_SNAPSHOT_PATH.exists():
            try:
                with open(MARKET_SNAPSHOT_PATH, "r") as f:
                    snapshot = json.load(f)
                    compact_lines = []
                    for ev_id, ev in snapshot.get("events", {}).items():
                        name = ev.get("en", "Unknown")
                        r_num = ev.get("raceNumber", "?")
                        runners = ev.get("runners", [])
                        run_strs = [f"{r.get('name', '?')} ({r.get('odds', '?')})" for r in runners]
                        compact_lines.append(f"[{name} Race {r_num}]: " + ", ".join(run_strs))
                    
                    compressed = "\n".join(compact_lines)
                    grounding_data += f"--- LIVE MARKET DATA ---\n{compressed[:15000]}\n"
            except:
                grounding_data += "--- LIVE MARKET DATA UNAVAILABLE ---\n"


        # 2. Classify intent via Regex PATTERNS
        intent = self.classifier.classify(message)

        # 1b. Smart LLM Router Fallback
        if not intent and not model_override:
            router_prompt = f"""You are the Strike Tips Router. Read the user message and output EXACTLY ONE of these intent strings, nothing else:
- get_account_summary (asking for balances, stats)
- evaluate_race (asking for tips, picks, analysis)
- run_daily_analysis (asking for today's races or a daily scan)
- record_selection (placing a bet or wager)
- calculate_probability_edge (odds math or probability calculations)
- calculate_max_position (asking for max stake or position size)
- search_past_races (asking about past races or memory)
- search_racing_data (looking for general racing rules/info or web search)
- update_race_result (settling a bet or reporting a win/loss)
- unknown (normal conversation)

Message: "{message}"
Intent:"""
            llm_intent = await self._call_ollama("racing_llama", router_prompt, system="You are an intent classifier. Output only the requested string.")
            if llm_intent:
                llm_intent = llm_intent.strip().lower()
                valid_intents = [
                    "get_account_summary", "evaluate_race", "run_daily_analysis", 
                    "record_selection", "search_racing_data", "calculate_probability_edge",
                    "calculate_max_position", "search_past_races", "update_race_result"
                ]
                # Clean up the response in case the model added extra text
                for v in valid_intents:
                    if v in llm_intent:
                        intent = v
                        logger.info(f"[SMART ROUTER] racing_llama classified intent as: {intent}")
                        break


        # 2. Grounding: Minimalist grounding to avoid context bloat
        grounding_data = ""
        if intent in ["evaluate_race", "run_daily_analysis", "search_racing_data"]:
            if self.strike and hasattr(self.strike, "memory"):
                # Use RAG memory instead of loading the whole JSON scan
                results = self.strike.memory.search_form_insights(message, n_results=3)
                if results:
                    bits = [r.get("content", "") for r in results]
                    grounding_data = f"\n--- RELEVANT MEMORY ---\n{chr(10).join(bits)}\n-----------------------\n"
                    logger.info(f"[GROUNDING] Loaded {len(results)} RAG bits.")

        # 3. Try direct tool execution (get live data)
        if intent:
            tool_response = await self._execute_tool(intent, message)
            if tool_response and tool_response.success:
                grounding_data += f"\n--- LIVE SYSTEM DATA from {intent} ---\n{tool_response.summary}\n--------------------------------------\n"


        # 4. Determine specialist model
        specialist = model_override or (
            self.classifier.get_specialist(intent) if intent else "racing_llama"
        )

        # 5. Build prompt with grounded history context
        context = "\n".join(
            f"{m['role'].upper()}: {m['content']}"
            for m in self._chat_history[-4:]
        )
        full_prompt = f"{grounding_data}{context}\nUSER: {message}\nASSISTANT (IMPORTANT: Synthesize any LIVE SYSTEM DATA provided above into a helpful response. Do NOT hallucinate or invent dates/races if they aren't in the data):"

        # 6. Try specialist model
        response_text = await self._call_ollama(specialist, full_prompt)


        # 6. Fallback chain if specialist fails
        if not response_text:
            for fallback in ModelFactory.FALLBACK_CHAIN:
                if fallback == specialist:
                    continue
                response_text = await self._call_ollama(fallback, full_prompt)
                if response_text:
                    specialist = fallback
                    break

        # 7. Cloud fallback
        if not response_text:
            response_text = await self._call_groq(full_prompt)
            specialist = "local:llama3.2:1b" if response_text else "unavailable"

        if not response_text:
            return AgentResponse(
                summary="Model is busy or loading. Please wait 30 seconds.",
                model_used="unavailable",
                confidence=0.0,
            )

        # 8. Update history
        self._chat_history.append({"role": "user", "content": message})
        self._chat_history.append({"role": "assistant", "content": response_text})
        self._chat_history = self._chat_history[-20:]  # Keep last 10 turns

        return AgentResponse(
            summary=response_text.strip(),
            model_used=specialist,
            confidence=0.85,
        )


# ─── Unified Orchestrator ─────────────────────────────────────────────────────

class UnifiedOrchestrator:
    """
    High-level orchestrator providing the public chat() API.
    Wraps ModelPipeline with history management, intent shortcuts,
    and memory grounding (ChromaDB RAG).
    """

    def __init__(self, strike_tips=None):
        self.strike = strike_tips
        self.pipeline = ModelPipeline(strike_tips)
        self._history: List[Dict] = []

    async def _handle_intents(self, message: str, is_user_msg: bool = True) -> Optional[str]:
        """
        Handle instant intents without LLM overhead.
        Returns a response string if intent is handled, else None.
        """
        msg_lower = message.lower().strip()

        if msg_lower in ("hi", "hello", "hey"):
            return "🏇 Strike Tips AI ready. Ask me about race cards, value bets, or your bankroll."

        if msg_lower in ("status", "balance", "bankroll"):
            if self.strike:
                try:
                    status = self.strike.get_bankroll_status()
                    return (
                        f"💰 Bankroll: R{status['current_bankroll']:.2f} | "
                        f"P&L: R{status['total_profit_loss']:.2f} | "
                        f"Open bets: {status['open_bets']}"
                    )
                except Exception:
                    pass

        return None

    async def chat(
        self, message: str, model_override: Optional[str] = None
    ) -> AgentResponse:
        """Main public API - process a user message and return AgentResponse"""
        # Try instant intent handlers first
        instant = await self._handle_intents(message)
        if instant:
            return AgentResponse(
                summary=instant,
                model_used="intent_handler",
                confidence=1.0,
            )

        # Delegate to pipeline
        response = await self.pipeline.chat(message, model_override=model_override)

        # Track history at orchestrator level
        self._history.append({"role": "user", "content": message})
        self._history.append({"role": "assistant", "content": response.summary})
        self._history = self._history[-20:]

        return response

    def clear_history(self):
        """Clear in-memory conversation history"""
        self._history = []
        self.pipeline._chat_history = []
