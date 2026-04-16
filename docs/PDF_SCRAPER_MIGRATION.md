# 📄 PDF-First Scraper Implementation Plan

This plan details the transition from brittle HTML scraping to robust PDF field extraction for TAB racing data.

## 🎯 Objective
Replace the dynamic HTML scraper in `tab4racing.py` with a dedicated PDF harvester that processes high-fidelity `Computaform` files directly from TAB's storage servers.

## 🛠️ Implementation Steps

### 1. Update `skills/parsers/pdf_harvester.py`
- Enhance the `PDFHarvester` class to handle remote PDF downloads using `httpx`.
- Implement `pypdf` text extraction logic to parse race cards, runners, and odds directly from the PDF stream.

### 2. Refactor `skills/parsers/tab4racing.py`
- Modify `TAB4RacingScraper` to:
    - Skip HTML scraping as the primary method.
    - Identify the correct PDF URL from the directory mapping discovered (e.g., `FieldsPDF/ComputaformSA/...`).
    - Delegate parsing to `PDFHarvester`.

### 3. Workflow Integration (`core_agent/core/strike_tips.py`)
- Update `run_daily_scan` to check for available PDFs first.
- If a valid PDF is found, use it as the source of truth for the scan.

## 🚀 Verification
- Run `docker exec -it strike-bot-new python core_agent/core/strike_tips.py scan`.
- Confirm logs indicate `[PDF] Processing: <pdf_url>` instead of `[STUB]` or HTML scraping warnings.
- Verify `data/pdf_cache/` is populated with clean extracted text.
