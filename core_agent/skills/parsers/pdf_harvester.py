import logging
import os
import re
import json
import httpx
import io
import fitz
from datetime import date
from typing import Dict, List, Optional
from bs4 import BeautifulSoup
from core_agent.skills.parsers.pdf_discovery import PDFDiscoveryService

logger = logging.getLogger("pdf-harvester")


class PDFHarvester:
    CDN_BASE = "https://aztabstorage.blob.core.windows.net/tabonline-blob/FieldsPDF"

    INTELLIGENCE_URLS = {
        "Computaform SA": f"{CDN_BASE}/ComputaformSA/{{track}}@{{date}}.pdf",
        "Daily Tips": f"{CDN_BASE}/Tips/TIPPINGSHEET@{{date}}.pdf",
    }

    SPONSORED_TRACKS = {
        "greyville": "HOLLYWOODBETS GREYVILLE",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join("data", "pdf_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_track_code(self, track: str) -> str:
        lowered = track.lower()
        if lowered in self.SPONSORED_TRACKS:
            return self.SPONSORED_TRACKS[lowered]
        return track.upper()

    async def get_latest_racing_intelligence(
        self,
        track: str,
        intelligence_type: str = "Computaform SA",
        specific_date: Optional[str] = None,
        precomputed_url: Optional[str] = None,
    ) -> Dict:
        today = specific_date or date.today().isoformat()
        cache_key = f"{track}_{intelligence_type}_{today}".replace(" ", "_").lower()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")

        if os.path.exists(cache_file):
            with open(cache_file) as f:
                return {**json.load(f), "cached": True}

        url = precomputed_url
        if not url:
            url_template = self.INTELLIGENCE_URLS.get(intelligence_type, "")
            formatted_date = today.replace("-", ".")
            url = url_template.format(
                track=self._get_track_code(track), date=formatted_date
            )

        from core_agent.core.http_client import get_async_client
        client = get_async_client(timeout=15)
        try:
            response = await client.get(url, follow_redirects=True)

            if response.status_code == 404:
                logger.info(
                    f"[PDF] 404 for {url}. Discovering dynamic URL for {track}..."
                )
                discovered_url = await PDFDiscoveryService.get_live_pdf_url(track, today)
                if discovered_url:
                    logger.info(f"[PDF] Discovery successful: {discovered_url}")
                    response = await client.get(
                        discovered_url, follow_redirects=True
                    )

            if response.status_code == 200:
                return await self._parse_pdf_bytes(
                    response.content, track, today, intelligence_type, cache_file
                )
        except Exception as e:
            logger.error(f"Download failed for {track}: {e}")

        return self._stub_intelligence(track, today)

    async def _parse_pdf_bytes(
        self,
        pdf_bytes: bytes,
        track: str,
        today: str,
        intelligence_type: str,
        cache_file: str,
    ) -> Dict:
        if pdf_bytes.strip().lower().startswith(b"<!"):
            return self._stub_intelligence(track, today)

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            raw_text = "\n".join(page.get_text() or "" for page in doc)
            doc.close()
        except Exception as e:
            logger.error(f"Failed to parse PDF for {track}: {e}")
            return self._stub_intelligence(track, today)

        tips = []
        current_race = None
        in_runner_block = False
        for line in raw_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            race_match = re.search(r"(?:RACE|R)\s*(\d+)", line, re.IGNORECASE)
            if race_match:
                current_race = int(race_match.group(1))
                in_runner_block = False
                continue
            if "NO- DR" in line and "HORSE" in line:
                in_runner_block = True
                continue
            if in_runner_block and current_race:
                runner_match = re.search(
                    r"^\d+\s*[-]?\s*\d+\s+([A-Z\s\'’]+?)(?=\s+\d+|$)", line
                )
                if runner_match:
                    name = runner_match.group(1).strip()
                    tips.append(
                        {
                            "race_number": current_race,
                            "selections": name,
                            "source": intelligence_type,
                        }
                    )

        result = {
            "source": intelligence_type,
            "track": track,
            "date": today,
            "parsed_tips": tips,
            "raw_text": raw_text[:50000],
            "cached": False,
        }
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        return result

    def _stub_intelligence(self, track: str, today: str) -> Dict:
        return {
            "source": "stub",
            "track": track,
            "date": today,
            "parsed_tips": [],
            "raw_text": "",
            "cached": False,
        }
