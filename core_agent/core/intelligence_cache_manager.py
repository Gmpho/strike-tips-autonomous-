import json
import os
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger("IntelligenceCache")


class IntelligenceCacheManager:
    """
    Manages persistence and rehydration of racing intelligence (odds history).
    Ensures that monitor restarts do not lose baseline prices.
    """

    def __init__(self, snapshot_path: str, cache_dir: str):
        self.snapshot_path = Path(snapshot_path)
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_state = {}

    def rehydrate(self) -> Dict[str, Any]:
        """Load state from the latest market snapshot."""
        if self.snapshot_path.exists():
            try:
                with open(self.snapshot_path, "r") as f:
                    data = json.load(f)
                    self.memory_state = data.get("events", {})
                    logger.info(
                        f"💾 Intelligence Cache: Rehydrated {len(self.memory_state)} events from disk."
                    )
                    return self.memory_state
            except Exception as e:
                logger.warning(f"⚠️ Intelligence Cache: Failed to rehydrate: {e}")
        return {}

    def update_baseline(self, event_id: str, runners: list):
        """Merge fresh odds into the historical record, preserving the earliest valid price as baseline."""
        cache_file = self.cache_dir / f"event_{event_id}.json"
        current_baseline = self.get_historical_odds(event_id)

        try:
            # Only consider valid numeric odds, ignore 'SP' or invalid floats
            new_odds = {}
            for r in runners:
                odds_val = r.get("odds")
                if odds_val and str(odds_val).upper() != "SP":
                    try:
                        new_odds[r["name"]] = float(odds_val)
                    except ValueError:
                        pass

            # Merge: Keep existing baseline if already present (earliest valid price wins)
            merged_baseline = {**new_odds, **current_baseline}

            state = {
                "event_id": event_id,
                "baseline_odds": merged_baseline,
                "last_updated": runners[0].get("last_updated") if runners else None,
            }
            with open(cache_file, "w") as f:
                json.dump(state, f)
        except Exception as e:
            logger.error(
                f"❌ Intelligence Cache: History sync failed for {event_id}: {e}"
            )

    def get_historical_odds(self, event_id: str) -> Dict[str, float]:
        """Fetch historical baseline for a specific event."""
        cache_file = self.cache_dir / f"event_{event_id}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    return json.load(f).get("baseline_odds", {})
            except:
                pass
        return {}

    def prune_stale_data(self, active_event_ids: list):
        """Remove baseline files for races that are no longer active."""
        try:
            active_ids = {str(eid) for eid in active_event_ids}
            pruned_count = 0

            for file in self.cache_dir.glob("event_*.json"):
                # Extract ID from filename: event_12345.json -> 12345
                file_id = file.stem.replace("event_", "")
                if file_id not in active_ids:
                    file.unlink()
                    pruned_count += 1

            if pruned_count > 0:
                logger.info(
                    f"🧹 Intelligence Cache: Pruned {pruned_count} finished races from disk."
                )
        except Exception as e:
            logger.error(f"❌ Intelligence Cache: Pruning failed: {e}")
