import os
from pathlib import Path

# Always define the root relative to the file location
# core_agent/config/paths.py -> ../.. -> root
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"

# Centralized path definitions
BANKROLL_PATH = DATA_DIR / "bankroll_state.json"
BET_HISTORY_PATH = DATA_DIR / "bet_history.json"
MARKET_SNAPSHOT_PATH = DATA_DIR / "market_snapshot_latest.json"
ATR_RESULTS_PATH = DATA_DIR / "atr_results_snapshot.json"
ATR_MOVERS_PATH = DATA_DIR / "atr_movers_snapshot.json"
ATR_PREDICTOR_PATH = DATA_DIR / "atr_predictor_snapshot.json"
NEWS_PATH = DATA_DIR / "news_latest.json"
NEWS_IMAGES_DIR = DATA_DIR / "news_images"
SWARM_INSIGHTS_PATH = DATA_DIR / "swarm_insights.json"
PDF_CACHE_DIR = DATA_DIR / "pdf_cache"
INTEL_CACHE_DIR = DATA_DIR / "intelligence_cache"
CHROMA_DIR = DATA_DIR / "chroma"

# Create subdirectories if they don't exist
os.makedirs(PDF_CACHE_DIR, exist_ok=True)
os.makedirs(INTEL_CACHE_DIR, exist_ok=True)
os.makedirs(CHROMA_DIR, exist_ok=True)
os.makedirs(NEWS_IMAGES_DIR, exist_ok=True)
