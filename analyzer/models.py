from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.

User = get_user_model()

class History(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='analyses')
    essay_text = models.TextField()
    ai_probability = models.FloatField()
    reasoning = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"History(id={self.id}, user={self.user.username}, prob={self.ai_probability:.2f})"
