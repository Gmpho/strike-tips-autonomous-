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


def calculate_scenario_shift(scenario: str, race_info: Dict, insight_text: str) -> float:
    """Calculate a mathematical probability shift based on going, wind, scratches, and sentiment."""
    scen_lower = scenario.lower()
    ins_lower = insight_text.lower()
    
    # 1. Going/Rain simulation
    if any(w in scen_lower for w in ("heavy", "soft", "rain", "wet", "mud")):
        # Check if form or name implies mud capability
        horse_name = race_info.get("name", "").lower()
        form_comments = race_info.get("form", "").lower()
        if any(w in horse_name or w in form_comments for w in ("mud", "wet", "rain", "heavy", "soft", "sire", "storm")):
            return 0.08
        return -0.05
        
    # 2. Wind simulation
    if any(w in scen_lower for w in ("wind", "headwind", "gale", "breeze")):
        form_comments = race_info.get("form", "").lower()
        # Pacesetters get penalized by headwinds
        if any(w in form_comments for w in ("led", "pace", "front", "speed")):
            return -0.06
        # Closers get boosted
        if any(w in form_comments for w in ("ran on", "stayed", "closer", "slowly away")):
            return 0.04
        return -0.01

    # 3. Scratch simulation
    if any(w in scen_lower for w in ("scratch", "withdrawn", "non-runner")):
        return 0.05

    # 4. Sentiment fallback from Groq/LLM insight
    positive_words = ("favor", "boost", "advantage", "value", "positive", "benefit", "strong", "win")
    negative_words = ("penalize", "downgrade", "negative", "hurt", "risk", "hazard", "weak", "lose")
    
    pos_count = sum(1 for w in positive_words if w in ins_lower)
    neg_count = sum(1 for w in negative_words if w in ins_lower)
    
    if pos_count > neg_count:
        return 0.05
    elif neg_count > pos_count:
        return -0.05
        
    return round(random.uniform(-0.03, 0.03), 3)


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
        prob_shift = calculate_scenario_shift(scenario, race, insight)

        dream = Dream(
            id=f"dream-{int(datetime.now().timestamp())}",
            timestamp=datetime.now().isoformat(),
            scenario=scenario,
            probability_shift=prob_shift,
            insight=insight,
            vividness=round(random.uniform(0.4, 0.95), 2),
            track=course,
            race=str(race_num),
        )
        self.history.insert(0, dream)
        if len(self.history) > 20:
            self.history.pop()

        # Parse decimal odds for win simulation
        try:
            odds_val = float(odds) if odds else 5.0
        except Exception:
            odds_val = 5.0

        # Simulate outcome (Bernoulli trial) based on odds and edge shift
        won = random.random() < ((1.0 / max(odds_val, 1.01)) * (1.0 + dream.probability_shift))

        # Record simulated result to LearningEngine
        try:
            from core_agent.skills.learning.engine import LearningEngine
            from core_agent.core.strike_brain import brain
            data_dir = brain.data_dir if brain else "./data"
            le = LearningEngine(data_dir=data_dir)
            le.record_dream_result(
                track=course,
                distance=1400,  # Default bucket if not specified in snapshot
                odds=odds_val,
                won=won
            )
        except Exception as e:
            logger.warning(f"Failed to record dream to learning engine: {e}")

        # Store dream in local ChromaDB for semantic stress-test lookups
        try:
            from core_agent.core.strike_brain import brain
            if brain and brain.memory and brain.memory._is_ready:
                meta = {
                    "type": "dream",
                    "track": course.lower(),
                    "race": str(race_num),
                    "scenario": scenario,
                    "probability_shift": dream.probability_shift,
                    "vividness": dream.vividness,
                    "timestamp": dream.timestamp,
                }
                brain.memory.add_form_insight(
                    horse=f"dream_{course.lower()}_r{race_num}",
                    insight=f"Scenario: {scenario} | Shift: {dream.probability_shift} | Vividness: {dream.vividness} | Insight: {insight}",
                    metadata=meta,
                )
                logger.info(f"[DREAM] Persisted dream to ChromaDB for {course} R{race_num}")
        except Exception as e:
            logger.warning(f"Failed to persist dream to ChromaDB: {e}")

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

    async def generate_custom_dream(self, track: str, race_num: int, scenario_override: str) -> Dream:
        snap = _load_snapshot()
        # Find matching race in snapshot
        target_race = None
        events = snap.get("events", {})
        for ev in events.values():
            course = (ev.get("course") or ev.get("venue") or "").lower()
            r_num = str(ev.get("raceNumber", ""))
            if track.lower() in course and r_num == str(race_num):
                target_race = ev
                break

        if not target_race:
            # Fallback to a mock race structure if not found in live snapshot
            target_race = {
                "course": track.title(),
                "raceNumber": str(race_num),
                "runners": [{"name": "Mock Runner", "odds": "5.0", "jockey": "Mock Jockey", "trainer": "Mock Trainer"}]
            }

        course = target_race.get("course", track.title())
        # Pick the favorite or first runner for context
        runners = target_race.get("runners", [])
        fav = runners[0] if runners else {}
        
        race_info = {
            "course": course,
            "raceNumber": str(race_num),
            "jockey": fav.get("jockeyName", fav.get("jockey", "Unknown Jockey")),
            "odds": fav.get("decimalOdds", fav.get("odds", "5.0")),
            "form": "No recent form data.",
            "name": fav.get("name", "Unknown Horse"),
            "trainer": fav.get("trainerName", fav.get("trainer", "Unknown Trainer"))
        }

        scenario = scenario_override
        insight = await _groq_insight(scenario, race_info)
        prob_shift = calculate_scenario_shift(scenario, race_info, insight)

        dream = Dream(
            id=f"dream-{int(datetime.now().timestamp())}",
            timestamp=datetime.now().isoformat(),
            scenario=scenario,
            probability_shift=prob_shift,
            insight=insight,
            vividness=round(random.uniform(0.4, 0.95), 2),
            track=course,
            race=str(race_num),
        )
        self.history.insert(0, dream)
        if len(self.history) > 20:
            self.history.pop()

        # Parse decimal odds for win simulation
        try:
            odds_val = float(race_info["odds"])
        except Exception:
            odds_val = 5.0

        # Simulate outcome (Bernoulli trial) based on odds and edge shift
        won = random.random() < ((1.0 / max(odds_val, 1.01)) * (1.0 + dream.probability_shift))

        # Record simulated result to LearningEngine
        try:
            from core_agent.skills.learning.engine import LearningEngine
            from core_agent.core.strike_brain import brain
            data_dir = brain.data_dir if brain else "./data"
            le = LearningEngine(data_dir=data_dir)
            le.record_dream_result(
                track=course,
                distance=1400,
                odds=odds_val,
                won=won
            )
        except Exception as e:
            logger.warning(f"Failed to record custom dream to learning engine: {e}")

        # Store dream in local ChromaDB for semantic stress-test lookups
        try:
            from core_agent.core.strike_brain import brain
            if brain and brain.memory and brain.memory._is_ready:
                meta = {
                    "type": "dream",
                    "track": course.lower(),
                    "race": str(race_num),
                    "scenario": scenario,
                    "probability_shift": dream.probability_shift,
                    "vividness": dream.vividness,
                    "timestamp": dream.timestamp,
                }
                brain.memory.add_form_insight(
                    horse=f"dream_{course.lower()}_r{race_num}",
                    insight=f"Scenario: {scenario} | Shift: {dream.probability_shift} | Vividness: {dream.vividness} | Insight: {insight}",
                    metadata=meta,
                )
                logger.info(f"[DREAM] Persisted custom dream to ChromaDB for {course} R{race_num}")
        except Exception as e:
            logger.warning(f"Failed to persist custom dream to ChromaDB: {e}")

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
