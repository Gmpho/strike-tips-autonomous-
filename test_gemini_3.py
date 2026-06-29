
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(".env")

def test_gemini_3():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    
    model_id = "gemini-3-flash-preview"
    
    # Simple tool
    def get_weather(city: str):
        return f"The weather in {city} is sunny."
        
    tools = [types.Tool(function_declarations=[
        types.FunctionDeclaration(
            name="get_weather",
            description="Get the weather for a city",
            parameters={
                "type": "object",
                "properties": {
                    "city": {"type": "string"}
                },
                "required": ["city"]
            }
        )
    ])]
    
    print(f"Testing {model_id}...")
    try:
        response = client.models.generate_content(
            model=model_id,
            contents="What is the weather in Durban?",
            config=types.GenerateContentConfig(
                tools=tools
            )
        )
        print("Response received!")
        if response.candidates[0].content.parts[0].function_call:
            print("Tool call detected!")
            print(response.candidates[0].content.parts[0].function_call)
        else:
            print("No tool call detected. Response text:")
            print(response.text)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_gemini_3()
