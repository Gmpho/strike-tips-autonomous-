
import os
from google import genai
from dotenv import load_dotenv

# Load env from root
load_dotenv()

def list_gemini_models():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("❌ GEMINI_API_KEY not found in .env")
        return

    client = genai.Client(api_key=api_key)
    
    print("📋 Fetching Gemini Model List...")
    print("-" * 50)
    try:
        # List all models
        models = list(client.models.list())
        for model in models:
            # The Model object has a 'name' attribute
            name = getattr(model, 'name', 'unknown')
            display_name = getattr(model, 'display_name', 'No display name')
            print(f"Model: {name}")
            print(f"  ID: {name.split('/')[-1]}")
            print(f"  Title: {display_name}")
            print("-" * 30)
        
        print(f"\n✅ Total models found: {len(models)}")
            
    except Exception as e:
        print(f"❌ Error fetching models: {e}")

if __name__ == "__main__":
    list_gemini_models()
