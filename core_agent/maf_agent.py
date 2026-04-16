import os
from dataclasses import dataclass
from typing import List, Dict, Optional
from core_agent.agents.specialists.bankroll_agent import BankrollSpecialist
from core_agent.agents.specialists.scanner_agent import ScannerSpecialist
from core_agent.agents.specialists.analyst_agent import AnalystSpecialist
from core_agent.config.model_config import ModelConfig

@dataclass
class AgentConfig:
    """Configuration and prompt loader for decoupled agents"""
    
    @staticmethod
    def load_prompt(agent_name: str) -> str:
        prompt_path = os.path.join("core_agent", "prompts", f"{agent_name}_agent.txt")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r") as f:
                return f.read()
        return "You are a helpful racing assistant."

    @staticmethod
    def get_model(role: str) -> str:
        # Dynamic model selection based on ModelConfig
        if role == "bankroll": return ModelConfig.REASONER
        if role == "scanner": return ModelConfig.SCRAPER
        if role == "analyst": return ModelConfig.REASONER
        return ModelConfig.ORCHESTRATOR

class StrikeMAFAgent:
    """
    Main Router / Orchestrator.
    Routes intents to specialized agents with dynamic model injection.
    """
    
    def __init__(self, strike_instance):
        self.strike = strike_instance
        
        # Specialist Agents with dynamic models
        self.specialists = {
            "bankroll": BankrollSpecialist(AgentConfig.load_prompt("bankroll")),
            "scanner": ScannerSpecialist(AgentConfig.load_prompt("scanner")),
            "analyst": AnalystSpecialist(AgentConfig.load_prompt("analyst"))
        }
        
    async def route_intent(self, intent: str, message: str):
        # Determine specialist based on intent mapping
        if intent in ["get_account_summary", "calculate_max_position", "record_selection"]:
            return await self.specialists["bankroll"].process(intent, message, self.strike)
        elif intent in ["run_daily_analysis", "verify_race_exists", "evaluate_race", "get_odds_snapshot"]:
            return await self.specialists["scanner"].process(intent, message, self.strike)
        elif intent in ["search_past_races", "search_racing_data", "calculate_probability_edge"]:
            return await self.specialists["analyst"].process(intent, message, self.strike)
        else:
            return "Intent not recognized."

def get_maf_agent(strike_instance):
    return StrikeMAFAgent(strike_instance)
