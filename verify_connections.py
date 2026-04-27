
import os
import asyncio
import httpx
from dotenv import load_dotenv

# Load env from root
load_dotenv()

async def test_groq():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return "❌ GROQ_API_KEY not found in .env"
    
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    payload = {
        "model": "llama-3.3-70b-versatile",
        "messages": [{"role": "user", "content": "Say 'Groq OK'"}],
        "max_tokens": 10
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if resp.status_code == 200:
                return "✅ Groq: Connection Successful (" + resp.json()['choices'][0]['message']['content'].strip() + ")"
            else:
                return f"❌ Groq: Error {resp.status_code} - {resp.text[:100]}"
    except Exception as e:
        return f"❌ Groq: Exception - {str(e)}"

async def test_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "❌ GEMINI_API_KEY not found in .env"
    
    url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Test with a STABLE model ID
    model_id = "gemini-pro"
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Say 'Gemini OK'"}],
        "max_tokens": 10
    }
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, headers=headers, json=payload, timeout=10.0)
            if resp.status_code == 200:
                return f"✅ Gemini ({model_id}): Connection Successful (" + resp.json()['choices'][0]['message']['content'].strip() + ")"
            else:
                return f"❌ Gemini ({model_id}): Error {resp.status_code} - {resp.text[:100]}"
    except Exception as e:
        return f"❌ Gemini ({model_id}): Exception - {str(e)}"

async def test_ollama_local():
    # Use localhost since we are outside the docker network
    host = "http://localhost:11434"
    url = f"{host}/api/tags"
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                return f"✅ Ollama Local ({host}): Connected ({len(models)} models found: {', '.join(models[:3])}...)"
            else:
                return f"❌ Ollama Local ({host}): Error {resp.status_code}"
    except Exception as e:
        return f"❌ Ollama Local ({host}): Connection Failed - Is Ollama running? ({str(e)})"

async def main():
    print("🏇 Verification of Strike Tips Cloud & Local Connections...")
    print("-" * 50)
    results = await asyncio.gather(
        test_groq(),
        test_gemini(),
        test_ollama_local()
    )
    for res in results:
        print(res)

if __name__ == "__main__":
    asyncio.run(main())
