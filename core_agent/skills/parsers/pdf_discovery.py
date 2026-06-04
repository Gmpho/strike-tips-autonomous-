import logging
from typing import Optional
from core_agent.core.http_client import get_async_client

logger = logging.getLogger("pdf-discovery")


class PDFDiscoveryService:
    API_URL = (
        "https://totex-col.4racing.com/PRODUCTS/webservice/phumelelaV4"
        "/get/Content/4RACINGWEB_TAB"
    )

    @classmethod
    async def get_live_pdf_url(
        cls, track: str, date_str: Optional[str] = None
    ) -> Optional[str]:
        from datetime import date
        today = date_str or date.today().isoformat()

        try:
            client = get_async_client(timeout=15)
            resp = await client.get(
                cls.API_URL,
                params={
                    "sub_action": "getComputaform",
                    "tag": "ComputaformSA",
                    "date": today,
                },
                headers={
                    "Accept": "application/json, text/plain, */*",
                    "Referer": "https://www.tab.co.za/",
                },
            )
            resp.raise_for_status()
            data = resp.json()

            pdfs = (data.get("data", {}) or {}).get("ComputaformSA", [])
            track_lower = track.lower()

            for pdf in pdfs:
                name = (pdf.get("name") or "").lower()
                if track_lower in name:
                    path = pdf.get("path")
                    if path:
                        logger.info(
                            f"[PDFDiscovery] Found matching PDF: {pdf['name']}"
                        )
                        return path

            logger.warning(f"[PDFDiscovery] No PDF found for track: {track}")
            return None

        except Exception as e:
            logger.error(f"[PDFDiscovery] API call failed: {e}")
            return None
