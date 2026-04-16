import logging
import os
import re
from datetime import date, datetime
from typing import Dict, List, Optional
import json
import httpx

logger = logging.getLogger("pdf-harvester")

class PDFHarvester:
    INTELLIGENCE_URLS = {
        "Computaform SA": "https://az-pgl-dsi-ag-cdn-aztabstorage.4racing.com/tabonline-blob/FieldsPDF/CF_ITW/{track}@{date}.pdf",
        "Daily Tips": "https://computaform.co.za/pdf/daily_tips_{date}.pdf",
    }

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = cache_dir or os.path.join("data", "pdf_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

    def _get_track_code(self, track: str) -> str:
        code_map = {
            'fairview': 'XFA', 
            'turffontein': 'XTD', 
            'greyville': 'XGR', 
            'vaal': 'XVA',
            'scottsville': 'XED',
            'kenilworth': 'XCP',
            'durbanville': 'XDU'
        }
        return code_map.get(track.lower(), track.upper())

    async def get_latest_racing_intelligence(self, track: str, intelligence_type: str = "Computaform SA", specific_date: Optional[str] = None, precomputed_url: Optional[str] = None) -> Dict:
        today = specific_date or date.today().isoformat()
        cache_key = f"{track}_{intelligence_type}_{today}".replace(" ", "_").lower()
        cache_file = os.path.join(self.cache_dir, f"{cache_key}.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file) as f:
                    data = json.load(f)
                return {**data, "cached": True}
            except Exception:
                pass
        
        if precomputed_url:
            url = precomputed_url
        else:
            url_template = self.INTELLIGENCE_URLS.get(intelligence_type, "")
            formatted_date = today.replace("-", ".")
            url = url_template.format(track=self._get_track_code(track), date=formatted_date)

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.get(url)
                logger.info(f"[PDF] Download attempt for {url}: {response.status_code}")
                if response.status_code == 200:
                    return await self._parse_pdf_bytes(response.content, track, today, intelligence_type, cache_file)
                else:
                    logger.warning(f"[PDF] Download failed with status {response.status_code}")
        except Exception as e:
            logger.warning(f"PDF download failed for {track}: {e}")
        return self._stub_intelligence(track, today)

    async def _parse_pdf_bytes(self, pdf_bytes: bytes, track: str, today: str, intelligence_type: str, cache_file: str) -> Dict:
        try:
            import pypdf
            import io
            reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
            raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except ImportError:
            logger.error("pypdf not installed")
            return self._stub_intelligence(track, today)
        
        tips = []
        current_race = None
        in_runner_block = False
        for line in raw_text.split('\n'):
            line = line.strip()
            if not line: continue
            race_match = re.search(r"(?:RACE|R)\s*(\d+)", line, re.IGNORECASE)
            if race_match:
                current_race = int(race_match.group(1))
                in_runner_block = False
                continue
            if "NO- DR" in line and "HORSE" in line:
                in_runner_block = True
                continue
            if any(x in line for x in ["COMPUTAFORM", "SPEED RATINGS", "COMMENT"]):
                in_runner_block = False
                continue
            if in_runner_block and current_race:
                runner_match = re.search(r'^\d+\s*[-]?\s*\d+\s+([A-Z\s\'’]+?)(?=\s+\d+|$)', line)
                if runner_match:
                    name = runner_match.group(1).strip()
                    tips.append({"race_number": current_race, "selections": name, "source": intelligence_type})
        result = {"source": intelligence_type, "track": track, "date": today, "parsed_tips": tips, "raw_text": raw_text[:2000], "cached": False}
        with open(cache_file, "w") as f:
            json.dump(result, f, indent=2)
        return result

    def _stub_intelligence(self, track: str, today: str) -> Dict:
        return {"source": "stub", "track": track, "date": today, "parsed_tips": [], "raw_text": "", "cached": False}
