import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from core_agent.agent.prompts import build_system_prompt
from core_agent.agent.providers.gemini import GeminiProvider

load_dotenv(".env")

async def test_payload():
    provider = GeminiProvider()
    print("API Key loaded:", bool(provider.api_key))
    
    system_prompt = build_system_prompt()
    
    # Simulate a user message
    messages = [
        {"role": "user", "content": "What is my account summary?"}
    ]
    
    contents = [
        {"role": "user", "parts": [{"text": m["content"]}]} for m in messages
    ]
    
    # Case 1: Test with standard prompt
    url = f"{provider.BASE}/gemini-2.0-flash:generateContent?key={provider.api_key}"
    payload_with_tools = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": contents,
        "generationConfig": {"maxOutputTokens": 400, "temperature": 0.3},
        "tools": provider._get_tools()
    }
    
    print("\n--- Testing Gemini with standard system prompt ---")
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload_with_tools)
        print("Status Code:", resp.status_code)
        if resp.status_code != 200:
            print("Response:", resp.text)
        else:
            print("Success!")
            data = resp.json()
            print("Response content:", json.dumps(data.get("candidates", [{}])[0].get("content", {}), indent=2))

if __name__ == "__main__":
    asyncio.run(test_payload())
