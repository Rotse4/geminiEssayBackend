from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()

class Wallet(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='wallet')
    balance = models.PositiveIntegerField(default=0)  # credits

    def __str__(self):
        return f"Wallet(user={self.user.username}, balance={self.balance})"

class PaymentTransaction(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'PENDING'),
        ('SUCCESS', 'SUCCESS'),
        ('FAILED', 'FAILED'),
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payments')
    amount = models.PositiveIntegerField()  # amount charged in KES
    credits = models.PositiveIntegerField()  # credits to grant on success
    phone = models.CharField(max_length=20)
    checkout_request_id = models.CharField(max_length=128, blank=True, null=True)
    merchant_request_id = models.CharField(max_length=128, blank=True, null=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default='PENDING')
    result_code = models.IntegerField(blank=True, null=True)
    result_desc = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payment(user={self.user.username}, amount={self.amount}, status={self.status})"