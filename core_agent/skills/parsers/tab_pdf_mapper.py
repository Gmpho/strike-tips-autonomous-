from typing import List, Dict
from core_agent.skills.race_analysis import RaceCard, Runner


def _map_pdf_to_races(intelligence: Dict, track: str) -> List[RaceCard]:
    """
    Maps parsed PDF tips into the RaceCard and Runner objects.
    Robust version that handles missing runner data.
    """
    races = []
    tips = intelligence.get("parsed_tips", [])
    if not tips:
        return []

    # Group tips by race number
    race_map = {}
    for tip in tips:
        r_num = tip.get("race_number")
        if r_num:
            if r_num not in race_map:
                race_map[r_num] = []
            race_map[r_num].append(tip.get("selections", "Unknown Horse"))

    for r_num, runners_list in race_map.items():
        runners = [
            Runner(horse_name=str(name).strip(), odds_decimal=5.0)
            for name in runners_list
            if name
        ]

        # Only add race if we have at least one runner identified
        if runners:
            races.append(
                RaceCard(
                    track=track,
                    race_number=r_num,
                    race_time="12:00",
                    track_condition="Good",
                    distance=1600,
                    runners=runners,
                )
            )
    return races
