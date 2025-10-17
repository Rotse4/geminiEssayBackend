import base64
import datetime
import json
import os
import requests
from dotenv import load_dotenv
from django.db import transaction
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from django.contrib.auth import get_user_model
from .models import Wallet, PaymentTransaction

User = get_user_model()

# Load env from .env if available
load_dotenv()

# Helpers

def get_or_create_wallet(user: User) -> Wallet:
    wallet, _ = Wallet.objects.get_or_create(user=user)
    return wallet


def mpesa_oauth_token():
    token = os.getenv('MPESA_BEARER_TOKEN')
    if token:
        return token
    basic = os.getenv('MPESA_BASIC_AUTH')
    if basic:
        headers = {'Authorization': f'Basic {basic}'}
        resp = requests.get('https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials', headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json().get('access_token')
    # Fallback to consumer key/secret if provided
    key = os.getenv('MPESA_CONSUMER_KEY')
    secret = os.getenv('MPESA_CONSUMER_SECRET')
    if not key or not secret:
        raise RuntimeError('MPESA credentials missing. Provide MPESA_BEARER_TOKEN or MPESA_BASIC_AUTH or CONSUMER_KEY/SECRET')
    auth = (key, secret)
    resp = requests.get('https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials', auth=auth, timeout=15)
    resp.raise_for_status()
    return resp.json().get('access_token')


def mpesa_password(short_code: str, passkey: str, timestamp: str) -> str:
    data = f"{short_code}{passkey}{timestamp}"
    return base64.b64encode(data.encode()).decode()


class InitiateStkPushView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request):
        # Expect {"credits": 10|20|50|100, "phone": "2547..."}
        credits = int(request.data.get('credits') or 0)
        phone = str(request.data.get('phone') or '').strip()
        if credits not in (10, 20, 50, 100):
            return Response({"error": "Invalid credits package. Allowed: 10,20,50,100"}, status=status.HTTP_400_BAD_REQUEST)
        if not phone.startswith('254'):
            return Response({"error": "Phone must be in international format starting with 254"}, status=status.HTTP_400_BAD_REQUEST)

        amount = credits  # 1 KES per credit (adjust if needed)
        short_code = os.getenv('MPESA_SHORT_CODE', '174379')
        # Support both MPESA_PASSKEY and legacy 'passkey'
        passkey = os.getenv('MPESA_PASSKEY') or os.getenv('passkey') or ''
        callback_url = os.getenv('MPESA_CALLBACK_URL', request.build_absolute_uri('/api/payments/callback/'))

        timestamp = timezone.now().strftime('%Y%m%d%H%M%S')
        password = os.getenv('MPESA_PASSWORD') or mpesa_password(short_code, passkey, timestamp)

        # Create local transaction record
        txn = PaymentTransaction.objects.create(
            user=request.user,
            amount=amount,
            credits=credits,
            phone=phone,
            status='PENDING'
        )

        token = mpesa_oauth_token()
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
        payload = {
            "BusinessShortCode": int(short_code),
            "Password": password,
            "Timestamp": timestamp,
            "TransactionType": "CustomerPayBillOnline",
            "Amount": amount,
            "PartyA": int(phone),
            "PartyB": int(short_code),
            "PhoneNumber": int(phone),
            "CallBackURL": callback_url,
            "AccountReference": "AIAnalyzer",
            "TransactionDesc": f"Purchase {credits} credits",
        }

        try:
            resp = requests.post('https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest',
                                 headers=headers, json=payload, timeout=30)
            data = resp.json() if resp.headers.get('content-type', '').startswith('application/json') else {}
            if resp.status_code != 200:
                txn.status = 'FAILED'
                txn.result_code = resp.status_code
                txn.result_desc = data.get('errorMessage') or resp.text
                txn.save(update_fields=['status', 'result_code', 'result_desc'])
                return Response({"error": "MPESA initiation failed", "details": txn.result_desc}, status=status.HTTP_400_BAD_REQUEST)

            txn.checkout_request_id = data.get('CheckoutRequestID')
            txn.merchant_request_id = data.get('MerchantRequestID')
            txn.result_desc = data.get('ResponseDescription')
            txn.save(update_fields=['checkout_request_id', 'merchant_request_id', 'result_desc'])
            return Response({"success": True, "checkout_request_id": txn.checkout_request_id}, status=status.HTTP_200_OK)
        except Exception as e:
            txn.status = 'FAILED'
            txn.result_desc = str(e)
            txn.save(update_fields=['status', 'result_desc'])
            return Response({"error": "Failed to contact MPESA", "details": str(e)}, status=status.HTTP_502_BAD_GATEWAY)


class MpesaCallbackView(APIView):
    permission_classes = [AllowAny]  # MPESA will call without auth

    @transaction.atomic
    def post(self, request):
        # Expect standard Daraja callback payload
        data = request.data if isinstance(request.data, dict) else json.loads(request.body.decode())
        body = data.get('Body', {})
        stk_callback = body.get('stkCallback', {})
        result_code = stk_callback.get('ResultCode')
        result_desc = stk_callback.get('ResultDesc')
        checkout_request_id = stk_callback.get('CheckoutRequestID')

        try:
            txn = PaymentTransaction.objects.select_for_update().get(checkout_request_id=checkout_request_id)
        except PaymentTransaction.DoesNotExist:
            # Unknown transaction; accept but do nothing
            return Response({"status": "ignored"}, status=status.HTTP_200_OK)

        txn.result_code = result_code
        txn.result_desc = result_desc
        if result_code == 0 or str(result_code) == '0':
            txn.status = 'SUCCESS'
            # Credit the wallet
            wallet = get_or_create_wallet(txn.user)
            wallet.balance = wallet.balance + txn.credits
            wallet.save(update_fields=['balance'])
        else:
            txn.status = 'FAILED'
        txn.save(update_fields=['status', 'result_code', 'result_desc'])
        return Response({"status": "ok"}, status=status.HTTP_200_OK)


class WalletView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        wallet = get_or_create_wallet(request.user)
        wallet.balance = 10
        wallet.save(update_fields=['balance'])
        return Response({"balance": wallet.balance})
        # return Response({"balance": wallet.balance})