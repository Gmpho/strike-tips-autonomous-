"""
Form Analyzer - SA Horse Racing Form Parser
Parses SA form strings (e.g. "1-2-1-3-4") and estimates win probability
based on recency, track/distance fit, and field size.
"""

import logging
import re
from typing import List, Optional, Tuple

logger = logging.getLogger("form-analyzer")

# SA Form position weights (more recent = higher weight)
RECENCY_WEIGHTS = [0.35, 0.25, 0.20, 0.12, 0.08]

# Track condition adjustments
CONDITION_MAP = {
    "good": 1.0,
    "soft": 0.95,
    "heavy": 0.90,
    "firm": 1.02,
    "synthetic": 0.98,
}


def parse_sa_form(form_string: str) -> List[int]:
    """
    Parse a SA form string into a list of finishing positions.
    Handles formats like "1-2-1", "1/2/3", "1 2 3", "1214" etc.
    Non-numeric entries (DNF, U, etc.) are treated as last place (99).

    Returns:
        List of ints, most recent run LAST (e.g. [4, 2, 1] = last was 1st)
    """
    if not form_string:
        return []

    # Normalize separators
    normalized = re.sub(r"[-/\s]+", " ", form_string.strip())

    positions = []
    for token in normalized.split():
        # Strip trailing letters (e.g. "1p", "2f")
        clean = re.sub(r"[^0-9]", "", token)
        if clean:
            pos = int(clean)
            positions.append(pos if pos > 0 else 99)
        else:
            positions.append(99)  # DNF/unknown

    return positions[-5:]  # Keep last 5 runs only


class FormAnalyzer:
    """
    Estimates win probability from SA form data using a weighted scoring model.
    Adjusts for track condition, target distance, and field size.
    """

    def estimate_win_probability(
        self,
        horse_name: str,
        form_positions: List[int],
        target_track: Optional[str] = None,
        target_distance: Optional[int] = None,
        track_condition: Optional[str] = None,
        field_size: int = 10,
    ) -> Tuple[float, float, str]:
        """
        Estimate win probability for a horse.

        Args:
            horse_name: Name of the horse
            form_positions: List of finishing positions (most recent last)
            target_track: Track being analyzed (for future track-specific adjustments)
            target_distance: Distance in metres
            track_condition: 'good', 'soft', 'heavy', 'firm', 'synthetic'
            field_size: Number of runners in the race

        Returns:
            (estimated_probability, form_rating, reasoning_text)
        """
        if not form_positions:
            # No form data — assign baseline probability
            baseline = 1.0 / max(field_size, 1)
            return (
                round(baseline, 4),
                0.0,
                f"No form data available. Baseline probability: {baseline:.1%}",
            )

        # 1. Weighted form score (0-1 scale, 1 = always wins)
        weights = RECENCY_WEIGHTS[: len(form_positions)]
        # Invert positions: position 1 → score 1.0, position 10 → score 0.1
        scores = []
        for i, pos in enumerate(reversed(form_positions)):
            score = max(0.0, 1.0 - (pos - 1) * 0.12)
            weighted_score = score * weights[i] if i < len(weights) else score * 0.05
            scores.append(weighted_score)

        form_rating = sum(scores)
        form_rating = min(form_rating, 1.0)

        # 2. Scale to win probability using field size
        # A horse with perfect form should win ~25-35% of the time in a 10-horse field
        field_factor = 1.0 / max(field_size, 1)
        base_prob = field_factor + (form_rating * 0.4)

        # 3. Apply track condition adjustment
        condition_key = (track_condition or "good").lower()
        condition_mult = CONDITION_MAP.get(condition_key, 1.0)
        adjusted_prob = base_prob * condition_mult

        # 4. Normalise — probability can't exceed 1/(field_size * 0.5)
        max_prob = min(0.75, 2.0 / max(field_size, 1))
        final_prob = min(adjusted_prob, max_prob)
        final_prob = max(final_prob, 0.01)  # floor at 1%

        # 5. Build reasoning text
        recent = form_positions[-3:] if len(form_positions) >= 3 else form_positions
        recent_str = "-".join(str(p) if p < 99 else "DNF" for p in recent)
        reasoning = (
            f"Form (last {len(form_positions)} runs): {recent_str} | "
            f"Rating: {form_rating:.2f} | "
            f"Condition: {condition_key} ({condition_mult:.2f}x) | "
            f"Est. probability: {final_prob:.1%}"
        )

        return (round(final_prob, 4), round(form_rating, 4), reasoning)
