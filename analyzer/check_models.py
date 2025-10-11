# check_models.py

import os
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Suppress informational logs from the Google library
logging.basicConfig(level=logging.WARNING)

print("Attempting to list available Gemini models...")

try:
    # Load the .env file to get the API key
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("\nERROR: GEMINI_API_KEY not found in .env file.")
    else:
        # Configure the genai library with your API key
        genai.configure(api_key=api_key)

        print("\nSuccessfully configured API key. Fetching models...\n")

        # List all models
        found_models = False
        for model in genai.list_models():
            # Check if the model supports the 'generateContent' method
            if 'generateContent' in model.supported_generation_methods:
                print(f"Model name: {model.name}")
                found_models = True

        if not found_models:
            print("\nNo models supporting 'generateContent' were found for your API key.")
            print("Please check if the 'Generative Language API' is enabled in your Google Cloud project.")

except Exception as e:
    print(f"\nAn unexpected error occurred: {e}")