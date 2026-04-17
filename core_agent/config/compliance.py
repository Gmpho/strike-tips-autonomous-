from typing import Dict, Any, List

# Compliance configuration for your primary intelligence targets
COMPLIANCE_CONFIG: Dict[str, Dict[str, Any]] = {
    "https://www.betway.co.za": {
        "tos_path": "/terms-and-conditions",
        "robots_check": "strict",
        "risk_level": "high", # Gambling - POPIA/SA strictness
        "data_type": "betting_odds",
        "emergency_stop": True
    },
    "https://www.tab4racing.com": {
        "tos_path": "/terms",
        "robots_check": "permissive",
        "risk_level": "medium",
        "data_type": "official_tote_data"
    }
}

# Legal Baseline for South Africa & Global
LEGAL_REQUIREMENTS = {
    "south_africa": [
        "POPIA compliance for horse/jockey data",
        "Gambling Act 2004 transparency",
        "Consumer Protection Act",
        "Do not cause server degradation"
    ],
    "global": [
        "Respect robots.txt",
        "Identify User-Agent clearly",
        "Limit crawl rate to human-like levels"
    ]
}

# Emergency Stop Trigger Procedures
EMERGENCY_PROCEDURES = {
    "tos_violation_detected": [
        "Immediate SIGTERM to monitor process",
        "Flush browser cache and rotate identity",
        "Notify admin via MessageGateway",
        "Cool down period: 24h"
    ],
    "legal_notice_received": [
        "Immediate wipe of browser profile",
        "Disable site-specific scraper",
        "Preserve audit log for compliance audit"
    ]
}
