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


def _enriched_race_text(course: str, race_num, runners: List[Dict]) -> str:
    """Betfair brief lines for one race (gear/days/comments/verdict).

    Reads the monitor's last-good cache directly — no extra fetching, no
    import coupling to the scan orchestrator. Empty string when unavailable.
    """
    try:
        data_dir = _dream_data_dir()
        with open(os.path.join(data_dir, "betfair_form_last_good.json")) as f:
            cache = json.load(f)
    except Exception:
        return ""
    import time as _time
    from datetime import datetime as _dt
    try:
        age = _time.time() - _dt.fromisoformat(cache.get("saved_at", "")).timestamp()
        if age > 6 * 3600:
            return ""
    except Exception:
        return ""
    want = {(r.get("name", "") or "").lower().strip() for r in runners if isinstance(r, dict)}
    lines = []
    for ev in (cache.get("events") or {}).values():
        if not isinstance(ev, dict):
            continue
        if str(ev.get("course", "")).lower() != str(course or "").lower():
            continue
        try:
            if int(ev.get("raceNumber", -1)) != int(race_num):
                continue
        except (ValueError, TypeError):
            continue
        for r in (ev.get("runners") or []):
            if not isinstance(r, dict):
                continue
            if (r.get("name", "") or "").lower().strip() not in want:
                continue
            bits = [str(r.get("name", "?"))]
            for field, short in (("gear", "gear"), ("daysSinceRun", "days"),
                                 ("official_rating", "OR"), ("runner_comments", "comment"),
                                 ("verdict", "verdict"), ("form", "form")):
                v = r.get(field)
                if v is None or v == "":
                    continue
                bits.append(f"{short}:{v}")
            lines.append(" | ".join(str(b) for b in bits)[:350])
    return "\n".join(lines[:12])


async def _groq_insight(scenario: str, race: Dict, enriched: str = "") -> str:
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
        f"Runners: {runner_summary}.{search_context}{chroma_context}"
        + (f"\nBetfair form: {enriched}" if enriched else "") +
        "\nGive one concise insight (1-2 sentences) on how this affects value/probability."
    )
    try:
        from core_agent.core import llm_cache as _llm_cache
        try:
            from core_agent.core.strike_brain import brain as _brain
            _ddir = getattr(_brain, "data_dir", None) or "./data"
        except Exception:
            _ddir = "./data"
        _hit = _llm_cache.get(_ddir, "dream-20b", prompt)
        if _hit:
            return _hit[:400]
    except Exception:
        _hit = None
    try:
        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=10.0, resolve_hosts={"api.groq.com"})
        resp = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-oss-20b", "messages": [{"role": "user", "content": prompt}], "max_tokens": 300, "temperature": 0.7},
        )
        if resp.status_code != 200:
            logger.warning(f"Groq dream failed: status {resp.status_code}")
            return "Simulation complete — insight unavailable."
        data = resp.json()
        if "choices" not in data or not data["choices"]:
            logger.warning("Groq dream failed: no 'choices' in response")
            return "Simulation complete — insight unavailable."
        content = (data["choices"][0]["message"].get("content") or "").strip()
        if not content:
            # Reasoning models may spend the whole budget on "reasoning";
            # surface it rather than returning a blank insight.
            reasoning = data["choices"][0]["message"].get("reasoning") or ""
            if reasoning:
                content = reasoning.strip()
        try:
            from core_agent.core import llm_cache as _llm_cache2
            try:
                from core_agent.core.strike_brain import brain as _brain2
                _ddir2 = getattr(_brain2, "data_dir", None) or "./data"
            except Exception:
                _ddir2 = "./data"
            if content:
                _llm_cache2.put(_ddir2, "dream-20b", prompt, content)
        except Exception:
            pass
        return content[:400]
    except Exception as e:
        logger.warning(f"Groq dream failed: {e}")
        return "Simulation complete — insight unavailable."


SCENARIO_TEMPLATES = [    "What if the going changed to Heavy at {course}?",
    "Simulating a 20km/h headwind on the straight at {course}.",
    "What if the favourite was a late scratch in Race {race}?",
    "Evaluating jockey substitution impact at {course} Race {race}.",
    "Calculating edge drift if market opens 30 minutes late at {course}.",
    "Simulating rain delay effect on {course} Race {race} odds.",
    "What if the distance was extended by 200m at {course}?",
    "Analysing outsider value if top trainer is suspended at {course}.",
    "What if the going turned Heavy while the draw bias shifted to gate 1 at {course}?",
    "Simulating a mid-race 4-runner reduction re-costing the market at {course} Race {race}.",
]


def _scenario_family(scenario: str) -> str:
    """Classify a scenario for calibration: going/wind/scratch/sentiment/other."""
    s = (scenario or "").lower()
    if any(w in s for w in ("heavy", "soft", "rain", "wet", "mud", "going", "delay")):
        return "going"
    if any(w in s for w in ("wind", "headwind", "gale", "breeze")):
        return "wind"
    if any(w in s for w in ("scratch", "withdrawn", "non-runner", "suspend", "reduction")):
        return "scratch"
    if any(w in s for w in ("late", "drift", "market", "distance", "outsider", "substitut")):
        return "sentiment"
    return "other"


def _dream_data_dir() -> str:
    try:
        from core_agent.core.strike_brain import brain
        if brain and getattr(brain, "data_dir", None):
            return str(brain.data_dir)
    except Exception:
        pass
    try:
        from core_agent.config.paths import DATA_DIR
        return str(DATA_DIR)
    except Exception:
        return "./data"


def _append_jsonl(data_dir: str, filename: str, record: Dict) -> None:
    try:
        with open(os.path.join(str(data_dir), filename), "a") as f:
            f.write(json.dumps(record, default=str) + "\n")
    except Exception as e:
        logger.debug(f"dream ledger append skipped: {e}")


def _record_dream_ledger(dream_id: str, date: str, track: str, race: str,
                         scenario: str, fav_name: str, fav_odds: float,
                         shift: float) -> None:
    """Append one prediction row: favorite, implied and shifted win probs."""
    try:
        implied = 1.0 / max(float(fav_odds), 1.01)
    except (ValueError, TypeError):
        implied = 0.2
    predicted = min(0.99, max(0.01, implied * (1.0 + float(shift or 0.0))))
    _append_jsonl(_dream_data_dir(), "dream_ledger.jsonl", {
        "dream_id": dream_id,
        "date": date,
        "track": str(track or ""),
        "race": str(race or ""),
        "family": _scenario_family(scenario),
        "fav": str(fav_name or ""),
        "odds": float(fav_odds) if fav_odds else None,
        "implied": round(implied, 4),
        "predicted": round(predicted, 4),
    })


def calibrate_dreams(data_dir: str = "") -> Dict[str, Any]:
    """Brier-score dream families against settled winners.

    Matches ledger rows to settled_winners by (date, track, race); skips
    dreams with no matching winner. Returns {family: {n, brier, baseline,
    skill}} and persists it to dream_calibration.json. Positive skill =
    dreams beat implied-only probability.
    """
    base = str(data_dir or _dream_data_dir())
    winners: Dict[tuple, str] = {}
    try:
        with open(os.path.join(base, "settled_winners.jsonl")) as f:
            for line in f:
                try:
                    w = json.loads(line)
                    winners[(str(w.get("date", ""))[:10],
                             str(w.get("track", "")).lower(),
                             str(w.get("race", "")))] = str(w.get("winner", ""))
                except Exception:
                    continue
    except Exception:
        return {}
    fams: Dict[str, Dict[str, float]] = {}
    try:
        with open(os.path.join(base, "dream_ledger.jsonl")) as f:
            rows = [json.loads(line) for line in f if line.strip()]
    except Exception:
        return {}
    for r in rows:
        try:
            key = (str(r.get("date", ""))[:10], str(r.get("track", "")).lower(), str(r.get("race", "")))
            winner = winners.get(key)
            if not winner:
                continue
            outcome = 1.0 if winner.lower() in str(r.get("fav", "")).lower() or str(r.get("fav", "")).lower() in winner.lower() else 0.0
            fam = str(r.get("family", "other"))
            b = fams.setdefault(fam, {"n": 0.0, "brier": 0.0, "baseline": 0.0})
            b["n"] += 1
            b["brier"] += (float(r.get("predicted", 0.0)) - outcome) ** 2
            b["baseline"] += (float(r.get("implied", 0.0)) - outcome) ** 2
        except Exception:
            continue
    out: Dict[str, Any] = {}
    for fam, b in fams.items():
        n = b["n"] or 1.0
        out[fam] = {
            "n": int(b["n"]),
            "brier": round(b["brier"] / n, 4),
            "baseline": round(b["baseline"] / n, 4),
            "skill": round((b["baseline"] - b["brier"]) / n, 4),
        }
    try:
        with open(os.path.join(base, "dream_calibration.json"), "w") as f:
            json.dump({"updated": datetime.now().isoformat(), "families": out}, f, indent=2)
    except Exception as e:
        logger.debug(f"calibration save skipped: {e}")
    return out


def calculate_scenario_shift(scenario: str, race_info: Dict, insight_text: str,
                             extra_text: str = "", deterministic: bool = False) -> float:
    """Calculate a mathematical probability shift based on going, wind, scratches, and sentiment.

    `extra_text` carries Betfair comment/verdict lines so keyword rules read
    real sentences instead of bare form strings. With deterministic=True the
    uninformative fallback is 0.0 (Tier-1 screens must be reproducible —
    never random).
    """
    scen_lower = scenario.lower()
    ins_lower = insight_text.lower()
    extra_lower = (extra_text or "").lower()

    def _hit(words, *texts):
        return any(w in t for w in words for t in texts if t)
    
    # 1. Going/Rain simulation
    if any(w in scen_lower for w in ("heavy", "soft", "rain", "wet", "mud")):
        # Check if form or name implies mud capability
        horse_name = race_info.get("name", "").lower()
        form_comments = race_info.get("form", "").lower()
        if _hit(("mud", "wet", "rain", "heavy", "soft", "sire", "storm"),
                horse_name, form_comments, extra_lower):
            return 0.08
        return -0.05

    # 2. Wind simulation
    if any(w in scen_lower for w in ("wind", "headwind", "gale", "breeze")):
        form_comments = race_info.get("form", "").lower()
        # Pacesetters get penalized by headwinds
        if _hit(("led", "pace", "front", "speed"), form_comments, extra_lower):
            return -0.06
        # Closers get boosted
        if _hit(("ran on", "stayed", "closer", "slowly away"), form_comments, extra_lower):
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

    if deterministic or not insight_text.strip():
        return 0.0
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

    async def generate_dream(self, allow_llm: bool = True) -> Dream:
        """Background dream. allow_llm=False runs the free deterministic
        Tier-1 screen (no Groq call) — the scheduler passes False for
        non-bet races (two-tier gating). Default True preserves behavior."""
        snap = _load_snapshot()
        race = _pick_race(snap)
        course = race.get("course", "Unknown Track")
        race_num = race.get("raceNumber", "?")
        # Jockey/odds/form live on runners, not on the event itself
        runners = race.get("runners", [])
        fav = runners[0] if runners else {}
        jockey = fav.get("jockeyName", fav.get("jockey", ""))
        odds = fav.get("decimalOdds", fav.get("odds", ""))
        distance = race.get("distance", "")
        trainer = fav.get("trainerName", fav.get("trainer", ""))
        weight = fav.get("weight", "")
        form = fav.get("form", "")


        scenario = random.choice(SCENARIO_TEMPLATES).format(course=course, race=race_num)
        enriched = _enriched_race_text(course, race_num, runners)
        if allow_llm:
            insight = await _groq_insight(scenario, race, enriched=enriched)
            prob_shift = calculate_scenario_shift(scenario, race, insight, extra_text=enriched)
        else:
            _fam = _scenario_family(scenario)
            insight = (f"Screened ({_fam} scenario, deterministic Tier-1, no LLM). "
                       f"{enriched[:220]}" if enriched else
                       f"Screened ({_fam} scenario, deterministic Tier-1, no LLM).")
            prob_shift = calculate_scenario_shift(
                scenario, race, "", extra_text=enriched, deterministic=True)

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
        try:
            from datetime import timezone as _tz, timedelta as _td
            _today = datetime.now(_tz(_td(hours=2))).strftime("%Y-%m-%d")
        except Exception:
            _today = datetime.now().strftime("%Y-%m-%d")
        _record_dream_ledger(
            dream.id, _today, course, str(race_num), scenario,
            str(fav.get("name", "")), odds if isinstance(odds, (int, float)) else 0.0,
            prob_shift,
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

        # Never persist fabricated races: mock data would pollute DSI queries
        # and LearningEngine priors for this track/race.
        if target_race is None:
            return Dream(
                id=f"dream-{int(datetime.now().timestamp())}",
                timestamp=datetime.now().isoformat(),
                scenario=scenario_override,
                probability_shift=0.0,
                insight=f"No live race data found for {track.title()} R{race_num} — simulation skipped to protect staking integrity.",
                vividness=0.0,
                track=track.title(),
                race=str(race_num),
            )

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
        try:
            from datetime import timezone as _tz, timedelta as _td
            _today = datetime.now(_tz(_td(hours=2))).strftime("%Y-%m-%d")
        except Exception:
            _today = datetime.now().strftime("%Y-%m-%d")
        try:
            _c_odds = float(race_info.get("odds", 0.0) or 0.0)
        except (ValueError, TypeError):
            _c_odds = 0.0
        _record_dream_ledger(
            dream.id, _today, course, str(race_num), scenario,
            str(race_info.get("name", "")), _c_odds, prob_shift,
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
