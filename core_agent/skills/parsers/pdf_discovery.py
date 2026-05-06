import logging
import httpx
from typing import Optional
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger("pdf-discovery")

class PDFDiscoveryService:
    """Discovers live PDF URLs by rendering the SPA portal via Playwright."""
    
    PORTAL_URL = "https://www.tab.co.za/tabs/content/horseracing_cards"

    @classmethod
    async def get_live_pdf_url(cls, track: str) -> Optional[str]:
        """Dynamically finds the PDF URL by simulating a user click."""
        logger.info(f"[PDFDiscovery] Simulating user click for track: {track}")
        browser = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto(cls.PORTAL_URL, wait_until="networkidle", timeout=60000)
                await page.wait_for_timeout(5000)
                content = await page.content()
                soup = BeautifulSoup(content, 'html.parser')
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    if track.lower() in href.lower() and href.endswith('.pdf'):
                        return urljoin("https://www.tab.co.za", href)
                logger.warning(f"[PDFDiscovery] No PDF found for track: {track}")
                return None
        except Exception as e:
            logger.error(f"[PDFDiscovery] Error rendering portal: {e}")
            return None
        finally:
            if browser:
                await browser.close()
