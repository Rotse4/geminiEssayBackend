# analyzer/views.py

import os
import google.generativeai as genai
from dotenv import load_dotenv
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.contrib.auth import get_user_model, authenticate
from django.db import transaction
from rest_framework.authtoken.models import Token
from .models import History
from zipfile import ZipFile
from io import BytesIO
import xml.etree.ElementTree as ET

# Load environment variables (for the API key)
load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class EssayAnalysisView(APIView):
    """
    An API View to analyze an essay for AI-generated content using the Gemini API.
    Requires authentication and stores the result in the user's history.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
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

            # Persist to history
            History.objects.create(
                user=request.user,
                essay_text=essay_text,
                ai_probability=float(analysis_result.get("ai_probability", 0.0)),
                reasoning=str(analysis_result.get("reasoning", "")),
            )

            return Response({"success": True, "results": analysis_result}, status=status.HTTP_200_OK)

        except Exception as e:
            # Handle potential errors from the API or JSON parsing
            return Response(
                {"error": "An error occurred during analysis.", "details": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class RegisterView(APIView):
    """Register a new user and return an auth token."""
    @transaction.atomic
    def post(self, request):
        username = request.data.get("username", "").strip()
        email = request.data.get("email", "").strip()
        password = request.data.get("password", "")

        if not username or not password:
            return Response({"error": "Username and password are required."}, status=status.HTTP_400_BAD_REQUEST)

        User = get_user_model()
        if User.objects.filter(username=username).exists():
            return Response({"error": "Username already taken."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(username=username, email=email or None, password=password)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username}, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    """Login with username and password; returns an auth token."""
    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "")
        user = authenticate(request, username=username, password=password)
        if not user:
            return Response({"error": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "username": user.username}, status=status.HTTP_200_OK)

class LogoutView(APIView):
    """Invalidate the current user's token (client should send Authorization header)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # Delete the current token to force re-login
        try:
            request.auth.delete()
        except Exception:
            pass
        return Response({"success": True}, status=status.HTTP_200_OK)

class HistoryListView(APIView):
    """List the authenticated user's history."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        items = History.objects.filter(user=request.user).values(
            "id", "ai_probability", "reasoning", "created_at"
        )
        # For privacy, don't return essay_text by default; toggle via query if needed
        include_text = request.query_params.get("include_text") == "1"
        if include_text:
            items = History.objects.filter(user=request.user).values(
                "id", "essay_text", "ai_probability", "reasoning", "created_at"
            )
        return Response({"results": list(items)}, status=status.HTTP_200_OK)

class UploadDocxView(APIView):
    """Accept a .docx upload and return extracted plain text."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        upload = request.FILES.get('file')
        if not upload:
            return Response({"error": "No file uploaded. Expected form field 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        filename = getattr(upload, 'name', '') or ''
        if not filename.lower().endswith('.docx'):
            return Response({"error": "Only .docx files are supported."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            data = upload.read()
            text = self._extract_docx_text(data)
            return Response({"success": True, "text": text}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": "Failed to read .docx file.", "details": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @staticmethod
    def _extract_docx_text(blob: bytes) -> str:
        """
        Minimal .docx text extractor with no external deps:
        - Opens the OOXML zip
        - Reads word/document.xml
        - Concatenates text from w:t nodes with basic paragraph separation
        """
        with ZipFile(BytesIO(blob)) as zf:
            with zf.open('word/document.xml') as doc_xml:
                xml_bytes = doc_xml.read()
        # Parse XML
        # The XML uses namespaces; we need to map w: prefix
        ns = {
            'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
        }
        root = ET.fromstring(xml_bytes)
        parts = []
        for para in root.findall('.//w:p', ns):
            runs = []
            for t in para.findall('.//w:t', ns):
                if t.text:
                    runs.append(t.text)
            if runs:
                parts.append(''.join(runs))
        return '\n\n'.join(parts).strip()
