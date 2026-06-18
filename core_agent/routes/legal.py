"""
Strike Tips - Legal Document Routes
Serves static legal documents (Privacy, Terms, Disclaimer) as Markdown.
"""

from fastapi import APIRouter, HTTPException, Response
from pathlib import Path
import os

router = APIRouter(prefix="/api/legal", tags=["legal"])

DOCS_DIR = Path(__file__).parent.parent.parent / "docs"

LEGAL_DOCS = {
    "privacy": "PRIVACY.md",
    "terms": "TERMS.md",
    "disclaimer": "DISCLAIMER.md",
    "how-to-bet": "HOW_TO_BET.md",
    "faq": "FAQ.md",
    "betting-rules": "BETTING_RULES.md",
    "responsible": "RESPONSIBLE.md",
}


@router.get("/{doc_name}")
async def get_legal_doc(doc_name: str):
    """Serve a legal document as Markdown"""
    if doc_name not in LEGAL_DOCS:
        raise HTTPException(status_code=404, detail="Document not found")

    file_path = DOCS_DIR / LEGAL_DOCS[doc_name]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Document file not found")

    content = file_path.read_text(encoding="utf-8")
    return Response(content=content, media_type="text/markdown")


@router.get("/")
async def list_legal_docs():
    """List available legal documents"""
    return {
        "documents": [
            {"id": k, "name": k.capitalize(), "url": f"/api/legal/{k}"}
            for k in LEGAL_DOCS.keys()
        ]
    }