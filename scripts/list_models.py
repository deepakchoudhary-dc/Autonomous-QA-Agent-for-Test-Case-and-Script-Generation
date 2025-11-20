import os
import google.generativeai as genai

api_key = os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise SystemExit("Please set the GOOGLE_API_KEY environment variable before running this script.")

genai.configure(api_key=api_key)
print("Listing available models...")
try:
    for model in genai.list_models():
        if 'generateContent' in getattr(model, 'supported_generation_methods', []):
            print(model.name)
except Exception as exc:
    print(f"Error listing models: {exc}")
