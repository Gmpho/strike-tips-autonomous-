import os
import json
import asyncio
import httpx
from dotenv import load_dotenv
from core_agent.agent.prompts import build_system_prompt
from core_agent.agent.providers.groq import GroqProvider

load_dotenv(".env")

async def test_payload():
    provider = GroqProvider()
    print("API Key loaded:", bool(provider.api_key))
    
    # Simulate a user message
    messages = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "user", "content": "What is my account summary?"}
    ]
    
    headers = {
        "Authorization": f"Bearer {provider.api_key}",
        "Content-Type": "application/json"
    }
    
    # Case 1: Test with tools
    payload_with_tools = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "system", "content": build_system_prompt()}] + messages,
        "max_tokens": 800,
        "temperature": 0.3,
        "tools": provider._get_tools()
    }
    
    print("\n--- Testing with tools ---")
    async with httpx.AsyncClient() as client:
        resp = await client.post(provider.URL, headers=headers, json=payload_with_tools)
        print("Status Code:", resp.status_code)
        if resp.status_code != 200:
            print("Response:", resp.text)
        else:
            print("Success!")

    # Case 2: Test without tools
    payload_without_tools = {
        "model": "llama-3.1-8b-instant",
        "messages": [{"role": "system", "content": build_system_prompt()}] + messages,
        "max_tokens": 800,
        "temperature": 0.3,
    }
    
    print("\n--- Testing without tools ---")
    async with httpx.AsyncClient() as client:
        resp = await client.post(provider.URL, headers=headers, json=payload_without_tools)
        print("Status Code:", resp.status_code)
        if resp.status_code != 200:
            print("Response:", resp.text)
        else:
            print("Success!")

if __name__ == "__main__":
    asyncio.run(test_payload())
