"""
Strike Brain - Central State Management
Unified provider for Racing Memory, Strike Tips, and Agent Tools.
Ensures singleton access across REST API and MCP interfaces.
"""

import os
import logging
from typing import Optional
from contextlib import asynccontextmanager

# Setup Logging
logger = logging.getLogger("strike-brain")


class StrikeBrain:
    _instance: Optional["StrikeBrain"] = None

    def __init__(self, data_dir: Optional[str] = None, enable_telegram: bool = True):
        # 🛡️ Docker Resilience: Use env var if present, otherwise fallback to centralized config
        from core_agent.config.paths import DATA_DIR as PROJECT_DATA_DIR

        env_data_dir = os.getenv("DATA_DIR")
        if env_data_dir:
            self.data_dir = env_data_dir
        else:
            # Use absolute path to the centralized directory
            self.data_dir = data_dir or str(PROJECT_DATA_DIR)

        self.chroma_dir = os.path.join(self.data_dir, "chroma")
        self.enable_telegram = enable_telegram

        # Core Components
        self.strike: Optional[StrikeTips] = None
        self.memory: Optional[RacingMemory] = None
        self.tools: Optional[AgentTools] = None
        self.ai: Optional[AIProvider] = None
        self.emergency_stop = False

        self._is_initialized = False

    @classmethod
    def get_instance(cls) -> "StrikeBrain":
        if cls._instance is None:
            # Respect DATA_DIR even in singleton access
            cls._instance = StrikeBrain()
        return cls._instance

    def initialize(self):
        """Synchronous initialization of core components"""
        if self._is_initialized:
            return

        logger.info("[MAF] Initializing Strike Brain...")

        # Domain Imports
        import sys

        if "/app" not in sys.path:
            sys.path.append("/app")

        from core_agent.core.strike_tips import StrikeTips
        from core_agent.skills.memory.chroma_memory import RacingMemory
        from core_agent.tools.maf_tool_registry import TOOL_REGISTRY as AgentTools

        # 1. Initialize Strike Tips (Orchestrator for Bankroll, Scraper, Analyzer)
        self.strike = StrikeTips(data_dir=self.data_dir, enable_telegram=True)

        # 2. Initialize Long-term Memory (ChromaDB Vector Store)
        self.memory = RacingMemory(data_dir=self.chroma_dir)

        # 3. Initialize Agent Tools (Functional capability layer)
        self.tools = AgentTools

        self._is_initialized = True
        logger.info("[MAF] Strike Brain initialized with 11 MAF tools")

    async def shutdown(self):
        """Graceful cleanup of resources"""
        if not self._is_initialized:
            return

        logger.info("[MAF] Strike Brain shutting down...")
        if self.strike:
            await self.strike.close()
        self._is_initialized = False
        logger.info("[OK] Strike Brain offline.")

    def set_emergency_stop(self, state: bool):
        """Toggle system-wide emergency stop"""
        self.emergency_stop = state
        logger.warning(f"[!!!] EMERGENCY STOP={'ON' if state else 'OFF'}")


# Global instance for easy access
brain = StrikeBrain.get_instance()


@asynccontextmanager
async def brain_lifespan(app=None):
    """FastAPI-compatible lifespan for the Brain"""
    brain.initialize()
    try:
        yield
    finally:
        await brain.shutdown()
