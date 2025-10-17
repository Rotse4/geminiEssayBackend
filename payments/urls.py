from django.urls import path
from .views import InitiateStkPushView, MpesaCallbackView, WalletView

urlpatterns = [
    path('payments/initiate/', InitiateStkPushView.as_view(), name='payments-initiate'),
    path('payments/callback/', MpesaCallbackView.as_view(), name='payments-callback'),
    path('wallet/', WalletView.as_view(), name='wallet'),
]