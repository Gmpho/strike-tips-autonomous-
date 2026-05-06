import re
from datetime import datetime
from typing import Dict, Any, List, Optional

class RaceMetadataManager:
    @staticmethod
    def extract_race_number(det: Dict[str, Any]) -> int:
        # Verified path: sportSpecificProperties.raceNumber
        return int(det.get('sportSpecificProperties', {}).get('raceNumber', 0))

    @staticmethod
    def extract_race_time(det: Dict[str, Any]) -> Optional[str]:
        # Use expectedStartEpoch for accurate start time
        start_epoch = det.get('expectedStartEpoch')
        if start_epoch:
            try:
                return datetime.fromtimestamp(start_epoch).strftime('%H:%M')
            except Exception:
                pass
        
        # Return None if time is not available
        return None

    @staticmethod
    def get_price(price_map: Dict[str, float], outcome_id: str) -> float:
        """Verified lookup for odds."""
        return float(price_map.get(outcome_id, 5.0))

    @staticmethod
    def process_runners(racers: List[Dict[str, Any]], price_map: Dict[str, float]) -> List[Dict[str, Any]]:
        runners = []
        seen_horse_names = set()
        
        for r in racers:
            horse_name = r.get("outcomeName") or r.get("name") or "Unknown"
            if horse_name in seen_horse_names:
                continue
            seen_horse_names.add(horse_name)
            
            outcome_ids = r.get("outcomeIds", [0])
            outcome_id = str(outcome_ids[0])
            odds = RaceMetadataManager.get_price(price_map, outcome_id)
            
            runner_obj = {
                "outcomeId": outcome_id,
                "name": horse_name,
                "outcomeName": horse_name,
                "jockeyName": r.get("jockeyName") or "TBA",
                "trainerName": r.get("trainerName") or "TBA",
                "age": r.get("age") or "U",
                "weight": r.get("weight") or "0",
                "form": r.get("form") or "",
                "number": r.get("number") or "0",
                "draw": int(r.get("draw", 0)),
                "timeForm": r.get("timeForm") or "",
                "imageLocation": r.get("imageLocation") or "",
                "odds": odds
            }
            # Omit starRating if not present in API
            rating = r.get("starRating")
            if rating is not None:
                runner_obj["starRating"] = str(rating)
            
            runners.append(runner_obj)
            
        return runners
