from core_agent.maf_agent import get_maf_agent
from core_agent.core.message_gateway import MessageGateway, Channel
import asyncio

# Mock class for StrikeTips dependency
class MockStrikeTips:
    def get_bankroll_status(self):
        return {"current_bankroll": 1000.0, "total_profit_loss": 0.0, "open_bets": 0}

async def run_gateway_to_maf_bridge():
    # 1. Initialize Gateway and MAF Agent
    gateway = MessageGateway()
    strike_instance = MockStrikeTips()
    maf_agent = get_maf_agent(strike_instance)
    
    print("--- Bridging Gateway to MAF Agent ---")
    
    # 2. Simulate incoming Telegram message
    user_msg = "What is my bankroll status?"
    result = gateway.process_message(
        message=user_msg,
        channel=Channel.TELEGRAM,
        user_id="user_123"
    )
    
    # 3. Map Gateway sanitized message to Intent
    # In a full system, you'd use your IntentClassifier here
    intent = "get_account_summary" 
    
    # 4. Route to MAF Agent
    print(f"Routing intent: {intent}")
    response = await maf_agent.route_intent(intent, result["message"])
    
    print(f"Final Agent Response: {response}")

if __name__ == "__main__":
    asyncio.run(run_gateway_to_maf_bridge())
