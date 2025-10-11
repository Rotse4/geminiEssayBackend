# analyzer/views.py

import os
import google.generativeai as genai
from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

# Load environment variables (for the API key)
load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class EssayAnalysisView(APIView):
    """
    An API View to analyze an essay for AI-generated content using the Gemini API.
    """
    def post(self, request, *args, **kwargs):
        print(f"reuest header: f{request}")
        essay_text = request.data.get('essay', '')

        # print(f"reuest header: f{request.data}")

        if not essay_text:
            return Response(
                {"error": "Essay text is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Initialize the Gemini Model
            model = genai.GenerativeModel('models/gemini-flash-latest')

            # This is the crucial part: The prompt engineering.
            # We ask the model to act as an expert and analyze the text based on specific criteria.
            prompt = f"""
            Analyze the following essay to determine the likelihood that it was written by an AI.
            Provide your response as a JSON object with two keys: 'ai_probability' and 'reasoning'.
            - 'ai_probability': A float value between 0.0 (definitely human) and 1.0 (definitely AI).
            - 'reasoning': A brief explanation for your score, considering factors like perplexity (predictability of text), burstiness (variation in sentence structure), and linguistic patterns.

            Essay to analyze:
            ---
            {essay_text}
            ---
            """

            # Get the response from the model
            response = model.generate_content(prompt)
            
            # The API returns a response that may contain markdown for JSON. 
            # We need to clean it up to parse it correctly.
            # Example response text: ```json\n{"key": "value"}\n```
            cleaned_json_str = response.text.replace('```json', '').replace('```', '').strip()

            # Convert the cleaned string to a Python dictionary
            import json
            analysis_result = json.loads(cleaned_json_str)
            print(f"analysis report {analysis_result} ")

            return Response({"success":True,"results":analysis_result}, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle potential errors from the API or JSON parsing
            return Response(
                {"error": "An error occurred during analysis.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )