"""
Core Brain - Strike Tips System
"""
from dataclasses import dataclass
from typing import Optional, Any

@dataclass
class StrikeDeps:
    """Dependency container for all Agent tools"""
    strike_tips: Any # Placeholder for the core engine
    memory: Any       # Chroma memory store
