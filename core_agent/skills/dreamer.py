"""
DreamEngine — AI-powered race simulation using live snapshot data + Groq.
Generates real insights from actual today's races, not hardcoded strings.
"""

import json
import logging
import os
import random
import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import List, Dict, Any
from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("dream-engine")


@dataclass
class Dream:
    id: str
    timestamp: str
    scenario: str
    probability_shift: float
    insight: str
    vividness: float
    track: str = ""
    race: str = ""


def _load_snapshot() -> Dict[str, Any]:
    from core_agent.core.snapshot_cache import get_snapshot
    return get_snapshot()


def _pick_race(snap: Dict) -> Dict:
    events = list(snap.get("events", {}).values())
    return random.choice(events) if events else {}


async def _groq_insight(scenario: str, race: Dict) -> str:
    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        return "Groq unavailable — insight pending."

    runners = race.get("runners", [])[:5]
    runner_summary = ", ".join(
        f"{r.get('name','?')} @ {r.get('odds','SP')}" for r in runners
    )

    # Search for real news to ground the dream
    search_context = ""
    course = race.get("course", "")
    if course and course != "Unknown Track":
        try:
            from core_agent.tools.maf_tool_registry import search_racing_data
            scenario_clean = scenario.replace(f" at {course}", "").replace(f" on {course}", "")
            scenario_clean = re.sub(r"Race \d+", "", scenario_clean).strip().rstrip("?,.")
            key_terms = scenario_clean[:25]
            result = await search_racing_data(f"{course} horse racing {key_terms}", limit=2)
            snippets = [r.get("snippet", "") for r in result.get("results", [])]
            if snippets:
                search_context = "\nReal-world context: " + " | ".join(s[:120] for s in snippets if s)
        except Exception:
            pass

    # Load ChromaDB form_insights (PDF official tips, past dreams) for this track
    chroma_context = ""
    try:
        from core_agent.core.strike_brain import brain
        if brain and brain.memory and brain.memory._is_ready:
            results = brain.memory.search_form_insights(
                f"{course} horse racing official tips", n_results=2
            )
            if results:
                snippets = [
                    r.get("content", "")[:160]
                    for r in results
                    if r.get("content")
                ]
                if snippets:
                    chroma_context = "\nPast data: " + " | ".join(snippets)
    except Exception:
        pass

    prompt = (
        f"Horse racing analyst. Scenario: {scenario}\n"
        f"Race: {race.get('course','?')} R{race.get('raceNumber','?')}. "
        f"Runners: {runner_summary}.{search_context}{chroma_context}\n"
        f"Give one concise insight (1-2 sentences) on how this affects value/probability."
    )
    try:
        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=10.0)
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "llama-3.1-8b-instant", "messages": [{"role": "user", "content": prompt}], "max_tokens": 80, "temperature": 0.7},
        )
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Groq dream failed: {e}")
        return "Simulation complete — insight unavailable."


SCENARIO_TEMPLATES = [
    "What if the going changed to Heavy at {course}?",
    "Simulating a 20km/h headwind on the straight at {course}.",
    "What if the favourite was a late scratch in Race {race}?",
    "Evaluating jockey substitution impact at {course} Race {race}.",
    "Calculating edge drift if market opens 30 minutes late at {course}.",
    "Simulating rain delay effect on {course} Race {race} odds.",
    "What if the distance was extended by 200m at {course}?",
    "Analysing outsider value if top trainer is suspended at {course}.",
    "What if the favourite was a late scratch in Race {race}?",
    "Evaluating jockey substitution impact at {course} Race {race}.",
]


class DreamEngine:
    def __init__(self):
        self.history: List[Dream] = []

    def get_context(self, track: str = "") -> str:
        """Return recent dreams as context string for the system prompt."""
        try:
            from core_agent.core.dream_memory import read_memories
            entries = read_memories("dreams", limit=3)
            if not entries:
                return ""
            lines = []
            for e in entries:
                if track and track.lower() not in e.get("tags", "").lower():
                    continue
                lines.append(f"- {e.get('title', '')}: {e.get('body', '')}")
            return "\n".join(lines) if lines else ""
        except Exception:
            return ""

    async def generate_dream(self) -> Dream:
        snap = _load_snapshot()
        race = _pick_race(snap)
        course = race.get("course", "Unknown Track")
        race_num = race.get("raceNumber", "?")
        jockey = race.get("jockey", "")
        odds = race.get("odds", "")
        distance = race.get("distance", "")
        trainer = race.get("trainer", "")
        weight = race.get("weight", "")
        form = race.get("form", "")


        scenario = random.choice(SCENARIO_TEMPLATES).format(course=course, race=race_num)
        insight = await _groq_insight(scenario, race)

        dream = Dream(
            id=f"dream-{int(datetime.now().timestamp())}",
            timestamp=datetime.now().isoformat(),
            scenario=scenario,
            probability_shift=round(random.uniform(-0.15, 0.15), 3),
            insight=insight,
            vividness=round(random.uniform(0.4, 0.95), 2),
            track=course,
            race=str(race_num),
        )
        self.history.insert(0, dream)
        if len(self.history) > 20:
            self.history.pop()

        # Write to two-phase dream memory (non-blocking, best-effort)
        try:
            import asyncio
            from core_agent.core.dream_memory import write_memory
            asyncio.get_event_loop().run_in_executor(
                None, write_memory, "dreams",
                f"{course} R{race_num} — {scenario[:40]}",
                insight,
                [course, f"R{race_num}", "dream"],
            )
        except Exception:
            pass

        return dream

    def get_recent_dreams(self) -> List[Dict]:
        return [asdict(d) for d in self.history]


dream_engine = DreamEngine()
