"""
HeartbeatEngine — OpenClaw-style agent heartbeat for Strike Tips.

Every 5 minutes:
  1. Generates a dream/insight from live race data via Groq
  2. Saves it to ChromaDB (form_insights collection) for RAG
  3. Writes data/heartbeat.md — injected into every agent prompt
  4. Prunes old entries to stay within token budget
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Optional

from core_agent.config.paths import MARKET_SNAPSHOT_PATH

logger = logging.getLogger("heartbeat")

HEARTBEAT_PATH = os.path.join("data", "heartbeat.md")
HEARTBEAT_INTERVAL = 300  # 5 minutes
MAX_HEARTBEAT_ENTRIES = 10  # keep last 10 in the md file


async def _run_heartbeat_tick(memory=None):
    """Single heartbeat tick: generate insight, save to ChromaDB, update heartbeat.md."""
    from core_agent.skills.dreamer import dream_engine

    try:
        # 1. Generate a real dream using live race data + Groq
        dream = await dream_engine.generate_dream()

        # 2. Save to ChromaDB for RAG retrieval
        if memory and memory._is_ready:
            memory.add_form_insight(
                horse=f"heartbeat_{dream.track}",
                insight=f"[{dream.timestamp}] {dream.scenario} → {dream.insight}",
                metadata={
                    "type": "heartbeat",
                    "track": dream.track,
                    "race": str(dream.race),
                    "probability_shift": str(dream.probability_shift),
                    "ts": dream.timestamp,
                },
            )

        # 3. Update heartbeat.md
        _update_heartbeat_md(dream)

        # 4. Telemetry push for the HUD sidebar stream
        try:
            from core_agent.core.telemetry import emit
            emit(
                "dream",
                f"🌀 {dream.track} R{dream.race} — {dream.scenario[:80]} → shift {dream.probability_shift:+.1%}",
            )
        except Exception:
            pass

        logger.info(f"💓 Heartbeat tick: {dream.track} — {dream.scenario[:60]}")

    except Exception as e:
        logger.warning(f"Heartbeat tick failed: {e}")


def _update_heartbeat_md(dream):
    """Append latest dream to heartbeat.md, keep last MAX_HEARTBEAT_ENTRIES."""
    try:
        # Read existing entries
        entries = []
        if os.path.exists(HEARTBEAT_PATH):
            with open(HEARTBEAT_PATH) as f:
                content = f.read()
            # Parse existing entries (each starts with "##")
            entries = [e.strip() for e in content.split("##") if e.strip() and not e.startswith("#")]

        # Add new entry
        new_entry = (
            f"## {dream.timestamp}\n"
            f"**Track:** {dream.track} | **Race:** {dream.race}\n"
            f"**Scenario:** {dream.scenario}\n"
            f"**Insight:** {dream.insight}\n"
            f"**Edge shift:** {dream.probability_shift:+.1%}\n"
        )
        entries.insert(0, new_entry)
        entries = entries[:MAX_HEARTBEAT_ENTRIES]

        # Write file
        os.makedirs(os.path.dirname(HEARTBEAT_PATH) or ".", exist_ok=True)
        with open(HEARTBEAT_PATH, "w") as f:
            f.write(f"# Strike Tips Heartbeat — Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
            f.write("\n".join(entries))

    except Exception as e:
        logger.warning(f"heartbeat.md write failed: {e}")


async def run_heartbeat_loop(memory=None):
    """Background loop — runs forever, ticks every HEARTBEAT_INTERVAL seconds."""
    logger.info(f"💓 Heartbeat loop started (interval: {HEARTBEAT_INTERVAL}s)")
    while True:
        await _run_heartbeat_tick(memory)
        await asyncio.sleep(HEARTBEAT_INTERVAL)
