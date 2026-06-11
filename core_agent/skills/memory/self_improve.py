"""
Self-Improvement Loop — Agent saves learned insights after complex tool chains.
Inspired by Hermes Agent's skill creation after 5+ tool calls + correction patching.
"""

import logging
from typing import Optional

logger = logging.getLogger("self-improve")


SELF_IMPROVE_NUDGE = (
    "\n\n=== SELF-IMPROVEMENT NUDGE ===\n"
    "If you just completed a multi-step analysis (5+ tool calls), consider saving "
    "the winning approach as a learned insight using save_learned_insight.\n"
    "Include: the pattern you used, key tools called, and the decision logic.\n"
    "This helps you reason faster on similar future queries."
)


def maybe_add_self_improve_nudge(tool_call_count: int, base_prompt: str) -> str:
    """Add self-improvement nudge if tool call count >= 5."""
    if tool_call_count >= 5:
        return base_prompt + SELF_IMPROVE_NUDGE
    return base_prompt


async def save_learned_insight(
    pattern_name: str,
    description: str,
    tool_sequence: list,
    key_insight: str,
    strike=None,
    **kwargs
) -> dict:
    """Save a learned analysis pattern as a ChromaDB insight (type=learned_insight)."""
    if not strike or not hasattr(strike, "memory") or not strike.memory._is_ready:
        return {"status": "ERROR", "reason": "Memory not available"}

    try:
        content = (
            f"=== LEARNED INSIGHT: {pattern_name} ===\n"
            f"Description: {description}\n"
            f"Tool sequence: {' → '.join(tool_sequence)}\n"
            f"Key insight: {key_insight}\n"
        )

        from core_agent.core.strike_brain import brain
        if brain and brain.memory and brain.memory._is_ready:
            success = brain.memory.add_form_insight(
                horse=pattern_name,
                insight=content,
                metadata={"type": "learned_insight", "pattern_name": pattern_name}
            )
            if success:
                return {"status": "SAVED", "pattern": pattern_name}
        return {"status": "ERROR", "reason": "Failed to save"}
    except Exception as e:
        logger.error(f"Save learned insight error: {e}")
        return {"status": "ERROR", "reason": str(e)}