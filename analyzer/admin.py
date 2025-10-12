from django.contrib import admin
from .models import History

@admin.register(History)
class HistoryAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "ai_probability", "created_at")
    list_filter = ("user", "created_at")
    search_fields = ("user__username", "reasoning", "essay_text")

# Register your models here.
