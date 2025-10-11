# analyzer/urls.py

from django.urls import path
from .views import EssayAnalysisView

urlpatterns = [
    path('analyze/', EssayAnalysisView.as_view(), name='analyze-essay'),
]