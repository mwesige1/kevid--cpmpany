from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [

    # ── Payment Flow ───────────────────────────────────
    # Called when customer clicks PAY NOW
    path(
        'initiate/',
        views.initiate_payment,
        name='initiate'
    ),

    # Called every 3 seconds by JavaScript polling
    path(
        'status/<int:order_id>/',
        views.payment_status,
        name='status'
    ),

    # ── Voucher Redemption ─────────────────────────────
    # Called when customer enters a voucher code
    path(
        'redeem-voucher/',
        views.redeem_voucher,
        name='redeem_voucher'
    ),

    # ── Mobile Money Callbacks ─────────────────────────
    # MTN sends payment result to this URL
    path(
        'mtn-callback/',
        views.mtn_callback,
        name='mtn_callback'
    ),

    # Airtel sends payment result to this URL
    path(
        'airtel-callback/',
        views.airtel_callback,
        name='airtel_callback'
    ),
    # IOTEC sends payment result to this URL
    path(
        'iotec-callback/',
        views.iotec_callback,
        name='iotec_callback'
    ),

    # Buy voucher via MoMo
    path(
        'buy-voucher/',
        views.buy_voucher,
        name='buy_voucher'
    ),
    # Check voucher payment status
    path(
        'buy-voucher/status/<int:order_id>/',
        views.buy_voucher_status,
        name='buy_voucher_status'
    ),
]