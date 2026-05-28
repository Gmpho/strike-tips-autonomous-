"""
Strike Tips - South African Horse Racing Intelligence System
Configuration Settings
"""

import os
from dataclasses import dataclass, field
from typing import List, Dict

# Load environment variables from .env file
from dotenv import load_dotenv

load_dotenv()


@dataclass
class BankrollConfig:
    """Bankroll management settings"""

    total_bankroll: float = 1000.0  # Starting bankroll in ZAR
    max_bet_percent: float = 5.0  # Max 5% per bet
    daily_loss_limit: float = 20.0  # Stop after 20% daily loss
    min_edge_threshold: float = 5.0  # Minimum 5% edge to bet
    kelly_fraction: float = 0.5  # Half-Kelly for safety
    currency: str = "ZAR"


@dataclass
class SARacingTracks:
    """South African racing tracks and their codes"""

    TRACKS: Dict[str, Dict] = field(
        default_factory=lambda: {
            "turffontein": {
                "name": "Turffontein Racecourse",
                "location": "Johannesburg",
                "surface": "turf",
                "tab_code": "XTD",
                "racing_days": ["Saturday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XTD",
            },
            "vaal": {
                "name": "Vaal Racecourse",
                "location": "Vereeniging",
                "surface": "turf",
                "tab_code": "XVA",
                "racing_days": ["Tuesday", "Thursday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XVA",
            },
            "fairview": {
                "name": "Fairview Racecourse",
                "location": "Gqeberha",
                "surface": "turf/poly",
                "tab_code": "XFA",
                "racing_days": ["Monday", "Friday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XFA",
            },
            "scottsville": {
                "name": "Scottsville",
                "location": "Pietermaritzburg",
                "surface": "turf",
                "tab_code": "XED",
                "racing_days": ["Sunday", "Wednesday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XED",
            },
            "kenilworth": {
                "name": "Kenilworth Racecourse",
                "location": "Cape Town",
                "surface": "turf",
                "tab_code": "XCP",
                "racing_days": ["Wednesday", "Saturday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XCP",
            },
            "durbanville": {
                "name": "Durbanville",
                "location": "Cape Town",
                "surface": "turf",
                "tab_code": "XDU",
                "racing_days": ["Occasional"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XDU",
            },
            "greyville": {
                "name": "Greyville Racecourse",
                "location": "Durban",
                "surface": "turf/poly",
                "tab_code": "XGR",
                "racing_days": ["Friday", "Sunday"],
                "url": "https://www.tab.co.za/tabs/horse/all/{date}/XGR",
            },
        }
    )


@dataclass
class NotificationConfig:
    """Telegram notification settings"""

    telegram_bot_token: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", "")
    )
    telegram_chat_id: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", "")
    )
    twa_url: str = field(
        default_factory=lambda: os.getenv("TELEGRAM_TWA_URL", "https://strike-tips-hud.vercel.app")
    )
    access_pin: str = field(
        default_factory=lambda: os.getenv("BOT_ACCESS_PIN", "")
    )
    enable_telegram: bool = True
    notification_time: str = "11:00"  # Daily scan time
    timezone: str = "Africa/Johannesburg"


@dataclass
class ScraperConfig:
    """Scraper settings"""

    request_timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 2
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    data_sources: List[str] = field(
        default_factory=lambda: ["tab4racing", "racing_post", "sa_racing"]
    )


# Global config instances
BANKROLL = BankrollConfig()
TRACKS = SARacingTracks().TRACKS
NOTIFICATIONS = NotificationConfig()
SCRAPER = ScraperConfig()
