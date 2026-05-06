import asyncio
import logging
import sys
import os

# Add the current directory to sys.path to allow imports from core_agent
sys.path.append(os.getcwd())

from core_agent.skills.parsers.pdf_discovery import PDFDiscoveryService
from core_agent.skills.parsers.pdf_harvester import PDFHarvester

logging.basicConfig(level=logging.INFO)

async def test_pdf_discovery():
    track = "Kenilworth"
    url = await PDFDiscoveryService.get_live_pdf_url(track)
    print(f"Discovered URL for {track}: {url}")
    
    if url:
        # We'll manually download and check the text
        import httpx
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, follow_redirects=True)
            if resp.status_code == 200:
                print(f"Downloaded PDF, size: {len(resp.content)} bytes")
                import pypdf
                import io
                reader = pypdf.PdfReader(io.BytesIO(resp.content))
                raw_text = "\n".join(page.extract_text() or "" for page in reader.pages)
                print("--- RAW TEXT PREVIEW (First 2000 chars) ---")
                print(raw_text[:2000])
                print("--- END PREVIEW ---")
                
                # Save it to a file for deeper inspection if needed
                with open("/home/giftmpho/Kimi_Agent_Strike Tips Racing Bot/core_agent/scratch/kenilworth_raw_text.txt", "w") as f:
                    f.write(raw_text)
            else:
                print(f"Failed to download PDF: {resp.status_code}")

if __name__ == "__main__":
    asyncio.run(test_pdf_discovery())
