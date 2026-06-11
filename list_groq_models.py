import os
import httpx
from dotenv import load_dotenv

load_dotenv()


def list_groq_models():
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("GROQ_API_KEY not found in .env")
        return

    print("Fetching Groq Model List...")
    print("-" * 60)
    try:
        resp = httpx.get(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()

        models = sorted(data.get("data", []), key=lambda m: m.get("id", ""))
        for m in models:
            mid = m.get("id", "?")
            owned = m.get("owned_by", "?")
            active = m.get("active", True)
            created = m.get("created", 0)
            print(f"  {mid}")
            print(f"    owned_by: {owned}  |  active: {active}")
            if created:
                from datetime import datetime
                dt = datetime.fromtimestamp(created)
                print(f"    created: {dt.strftime('%Y-%m-%d')}")
            print()

        print(f"Total models found: {len(models)}")

    except Exception as e:
        print(f"Error fetching models: {e}")


if __name__ == "__main__":
    list_groq_models()