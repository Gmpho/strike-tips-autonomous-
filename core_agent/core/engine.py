"""
Strike Tips - South African Horse Racing Intelligence System
Main orchestrator that ties together all skills.
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Optional
from dataclasses import asdict

# Absolute Imports for core_agent structure
from skills.race_analysis import RaceAnalyzer, RaceCard, Runner
from skills.race_analysis.form_analyzer import FormAnalyzer, parse_sa_form
from skills.bankroll_manager import BankrollGovernor
from skills.parsers.tab4racing import TAB4RacingScraper, ScrapedRunner, ScrapedRace
from skills.parsers.self_healing import SelfHealingParser
from skills.notifications.telegram_bot import TelegramNotifier
from agents.ai_providers import AIProvider
from config.settings import BANKROLL, TRACKS

logger = logging.getLogger("strike-tips-engine")

class StrikeTips:
    """
    Main Strike Tips orchestrator.
    Coordinates scraping, analysis, bankroll management, and notifications.
    """

    def __init__(self, data_dir: str = "./data", enable_telegram: bool = True):
        self.data_dir = os.path.abspath(data_dir)
        os.makedirs(self.data_dir, exist_ok=True)

        # Initialize core components
        self.analyzer = RaceAnalyzer()
        self.form_analyzer = FormAnalyzer()
        self.bankroll = BankrollGovernor(data_dir=self.data_dir)
        self.scraper = TAB4RacingScraper()
        self.parser = SelfHealingParser()
        self.ai = AIProvider()
        
        # Initialize Memory
        from skills.memory.chroma_memory import RacingMemory
        self.memory = RacingMemory(data_dir=os.path.join(self.data_dir, "chroma"))

        self._processing_tracks = set()

        self.telegram = None
        if enable_telegram:
            try:
                self.telegram = TelegramNotifier()
            except ValueError as e:
                logger.warning(f"Telegram not configured: {e}")

    async def scrape_and_analyze_track(self, track: str, date_str: Optional[str] = None) -> List[Dict]:
        """Scrape and analyze all races at a track."""
        track_key = f"{track}_{date_str or 'today'}"
        if track_key in self._processing_tracks:
            return []
            
        self._processing_tracks.add(track_key)
        try:
            races = await self.scraper.scrape_racecard(track, date_str)
            if not races:
                return []
            
            # (Analysis logic follows...)
            return []
        finally:
            self._processing_tracks.remove(track_key)

    async def close(self):
        """Clean up resources."""
        await self.scraper.close()
        if self.telegram:
            self.telegram.close()
