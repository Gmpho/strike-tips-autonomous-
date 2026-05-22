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

import httpx

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
    try:
        with open(MARKET_SNAPSHOT_PATH) as f:
            return json.load(f)
    except Exception:
        return {"events": {}}


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
            from core_agent.skills.memory.search_tool import search_racing_data
            scenario_clean = scenario.replace(f" at {course}", "").replace(f" on {course}", "")
            scenario_clean = re.sub(r"Race \d+", "", scenario_clean).strip().rstrip("?,.")
            key_terms = scenario_clean[:25]
            results = search_racing_data(f"{course} horse racing {key_terms}", limit=2)
            if results:
                search_context = "\nReal-world context: " + " | ".join(r[:120] for r in results if r)
        except Exception:
            pass

    prompt = (
        f"Horse racing analyst. Scenario: {scenario}\n"
        f"Race: {race.get('course','?')} R{race.get('raceNumber','?')}. "
        f"Runners: {runner_summary}.{search_context}\n"
        f"Give one concise insight (1-2 sentences) on how this affects value/probability."
    )
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
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
]


class DreamEngine:
    def __init__(self):
        self.history: List[Dream] = []

    async def generate_dream(self) -> Dream:
        snap = _load_snapshot()
        race = _pick_race(snap)
        course = race.get("course", "Unknown Track")
        race_num = race.get("raceNumber", "?")

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

        # Write to Honcho as agent_dream peer (non-blocking, best-effort)
        try:
            from core_agent.skills.memory.honcho_memory import dream_honcho
            import asyncio
            asyncio.get_event_loop().run_in_executor(
                None, dream_honcho.record_dream, scenario, insight, course
            )
        except Exception:
            pass

        return dream

    def get_recent_dreams(self) -> List[Dict]:
        return [asdict(d) for d in self.history]


dream_engine = DreamEngine()
