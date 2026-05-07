"""
Strike Tips - Racing Service
Centralizes racing analysis, scraping, and PDF harvesting.
"""

import os
import json
import asyncio
from typing import List, Dict, Optional, Any
from datetime import date
from dataclasses import asdict

# Import existing skills
from core_agent.skills.parsers.tab4racing import TAB4RacingScraper, ScrapedRace
from core_agent.skills.parsers.pdf_harvester import PDFHarvester
from core_agent.skills.race_analysis import RaceAnalyzer, RaceCard, Runner
from core_agent.skills.race_analysis.form_analyzer import FormAnalyzer, parse_sa_form
from core_agent.agents.ai_providers import AIProvider
from core_agent.config.settings import BANKROLL


class RacingService:
    def __init__(self):
        self.scraper = TAB4RacingScraper()
        self.harvester = PDFHarvester()
        self.analyzer = RaceAnalyzer()
        self.form_analyzer = FormAnalyzer()
        self.ai = AIProvider()
        self._processing_tracks = set()

    async def get_intelligence(
        self,
        track: str,
        intelligence_type: str = "Computaform SA",
        specific_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Proactively harvest and parse intelligence."""
        # Warm cache first
        await self.harvester.get_latest_racing_intelligence(
            track=track,
            intelligence_type=intelligence_type,
            specific_date=specific_date,
        )
        # Fetch/Return
        return await self.harvester.get_latest_racing_intelligence(
            track=track,
            intelligence_type=intelligence_type,
            specific_date=specific_date,
        )

    async def scan_and_analyze(
        self, track: str, date_str: Optional[str] = None
    ) -> List[Dict]:
        """Scrape and analyze track."""
        track_key = f"{track}_{date_str or date.today().isoformat()}"
        if track_key in self._processing_tracks:
            return []

        self._processing_tracks.add(track_key)
        try:
            # Pre-warm
            await self.harvester.get_latest_racing_intelligence(
                track=track, intelligence_type="Computaform SA", specific_date=date_str
            )

            # Scrape
            races = await self.scraper.scrape_racecard(track, date_str)
            if not races:
                return []

            # Analyze
            prompts = []
            race_mappings = []
            for race in races:
                race_card, probs, reason = self._convert_race_data(race)
                prompts.append(self.ai._build_race_prompt(asdict(race)))
                race_mappings.append((race, race_card, probs, reason))

            ai_results = await self.ai._call_kimi_parallel(prompts)

            results = []
            for i, ai_res in enumerate(ai_results):
                race, race_card, probs, reason = race_mappings[i]
                bets = self.analyzer.analyze_race(race_card, probs, reason)
                results.append(
                    {
                        "track": race.track,
                        "race_number": race.race_number,
                        "race_time": race.race_time,
                        "distance": race.distance,
                        "condition": race.track_condition,
                        "runners": len(race.runners),
                        "value_bets": [asdict(vb) for vb in bets],
                        "ai_insight": (
                            ai_res.content[:500] + "..."
                            if ai_res.content
                            else "No insight"
                        ),
                    }
                )

            return results
        finally:
            self._processing_tracks.remove(track_key)

    def _convert_race_data(self, scraped_race: ScrapedRace) -> tuple:
        """Helper to convert scraped race data to internal format."""
        runners = []
        probs = {}
        reasoning = {}
        for sr in scraped_race.runners:
            form = parse_sa_form(sr.form) if sr.form else []
            prob, rating, reason = self.form_analyzer.estimate_win_probability(
                sr.horse_name,
                form,
                target_track=scraped_race.track,
                target_distance=scraped_race.distance,
                track_condition=scraped_race.track_condition.lower(),
                field_size=len(scraped_race.runners),
            )
            runners.append(
                Runner(
                    horse_name=sr.horse_name,
                    odds_decimal=sr.odds_decimal,
                    jockey=sr.jockey,
                    trainer=sr.trainer,
                    barrier=sr.barrier,
                    weight=sr.weight,
                    last_5_runs=form,
                )
            )
            probs[sr.horse_name] = prob
            reasoning[sr.horse_name] = reason

        return (
            RaceCard(
                track=scraped_race.track,
                race_number=scraped_race.race_number,
                race_time=scraped_race.race_time,
                distance=scraped_race.distance,
                track_condition=scraped_race.track_condition,
                runners=runners,
            ),
            probs,
            reasoning,
        )
