# analyzer/urls.py

from django.urls import path
from .views import EssayAnalysisView, RegisterView, LoginView, LogoutView, HistoryListView, UploadDocxView

urlpatterns = [
    path('analyze/', EssayAnalysisView.as_view(), name='analyze-essay'),
    path('auth/register/', RegisterView.as_view(), name='register'),
    path('auth/login/', LoginView.as_view(), name='login'),
    path('auth/logout/', LogoutView.as_view(), name='logout'),
    path('history/', HistoryListView.as_view(), name='history-list'),
    path('upload-docx', UploadDocxView.as_view(), name='upload-docx'),  # no trailing slash to match frontend
]
