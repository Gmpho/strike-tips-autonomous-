import asyncio
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
import aiohttp
from bs4 import BeautifulSoup

# Base models for consistency
from dataclasses import dataclass

logger = logging.getLogger("FastScraper")

class FastScraper:
    """
    Tier 3 Intelligence: High-speed HTML parser using BeautifulSoup/lxml.
    Ported from User's Gold Standard Project.
    """

    def __init__(self, ai_client=None, timeout: int = 15):
        self.ai_client = ai_client
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
        
        self.stats = {
            "request_count": 0,
            "success_count": 0,
            "error_count": 0
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Fetch, clean, and intelligently extract data from a static URL."""
        self.stats["request_count"] += 1
        
        try:
            session = await self._get_session()
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1"
            }

            async with session.get(url, headers=headers) as response:
                if response.status != 200:
                    self.stats["error_count"] += 1
                    return {"success": False, "error": f"HTTP {response.status}"}
                
                html = await response.text()
                
            # Tier 3 Logic: Speed Cleaning
            clean_content = self._parse_and_clean_html(html)
            
            # Intelligent Extraction (AI Fallback)
            races = []
            if self.ai_client:
                races = await self.ai_client.extract_race_data(clean_content, url)
            
            self.stats["success_count"] += 1
            return {
                "success": True,
                "races": races,
                "source": url,
                "strategy": "BEAUTIFULSOUP"
            }

        except Exception as e:
            self.stats["error_count"] += 1
            logger.error(f"FastScraper Error: {e}")
            return {"success": False, "error": str(e)}

    def _parse_and_clean_html(self, html: str) -> str:
        """
        User's Speed-Reader logic:
        1. Parse with lxml (fastest)
        2. Strip noise (scripts, styles, meta)
        3. Normalize whitespace
        """
        try:
            soup = BeautifulSoup(html, 'lxml')
            
            # Decompose heavy/noisy tags
            for tag in soup(['script', 'style', 'noscript', 'meta', 'link', 'svg', 'iframe']):
                tag.decompose()
                
            # Extract main text content
            text = soup.get_text(separator=' ')
            
            # Normalize whitespace
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
            
        except Exception as e:
            logger.warning(f"Cleanup failed, returning raw: {e}")
            return html

    async def close(self):
        if self.session:
            await self.session.close()

    def get_stats(self) -> Dict:
        return self.stats
