"""
Strike Tips - Intent Classifier
Thin wrapper — delegates to the IntentClassifier in ai_pydantic.py.
Kept for backward compat with any code that imports from this module.
"""

from core_agent.agents.ai_pydantic import IntentClassifier
from core_agent.agents.schemas import IntentResponse

__all__ = ["IntentClassifier", "IntentResponse"]
