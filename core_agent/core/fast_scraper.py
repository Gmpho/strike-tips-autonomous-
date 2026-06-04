import asyncio
import re
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from bs4 import BeautifulSoup

from core_agent.core.http_client import get_async_client

logger = logging.getLogger("FastScraper")


class FastScraper:
    """
    Tier 3 Intelligence: High-speed HTML parser using BeautifulSoup/lxml.
    Ported from User's Gold Standard Project.
    Uses curl_cffi with rotating proxies + TLS fingerprint spoofing.
    """

    def __init__(self, ai_client=None, timeout: int = 15):
        self.ai_client = ai_client
        self.timeout = timeout
        self.stats = {"request_count": 0, "success_count": 0, "error_count": 0}

    async def scrape(self, url: str) -> Dict[str, Any]:
        """Fetch, clean, and intelligently extract data from a static URL."""
        self.stats["request_count"] += 1

        try:
            client = get_async_client(timeout=self.timeout)
            headers = {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
            }

            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                self.stats["error_count"] += 1
                return {"success": False, "error": f"HTTP {response.status_code}"}

            html = response.text

            clean_content = self._parse_and_clean_html(html)

            races = []
            if self.ai_client:
                races = await self.ai_client.extract_race_data(clean_content, url)

            self.stats["success_count"] += 1
            return {
                "success": True,
                "races": races,
                "source": url,
                "strategy": "BEAUTIFULSOUP",
            }

        except Exception as e:
            self.stats["error_count"] += 1
            logger.error(f"FastScraper Error: {e}")
            return {"success": False, "error": str(e)}

    def _parse_and_clean_html(self, html: str) -> str:
        try:
            soup = BeautifulSoup(html, "lxml")
            for tag in soup(
                ["script", "style", "noscript", "meta", "link", "svg", "iframe"]
            ):
                tag.decompose()
            text = soup.get_text(separator=" ")
            text = re.sub(r"\s+", " ", text)
            return text.strip()
        except Exception as e:
            logger.warning(f"Cleanup failed, returning raw: {e}")
            return html

    async def close(self):
        pass

    def get_stats(self) -> Dict:
        return self.stats
