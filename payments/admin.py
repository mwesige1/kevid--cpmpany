from django.contrib import admin
from .models import Order, Withdrawal, VoucherAgent, Voucher


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """
    Admin configuration for payment orders.
    Shows all payment attempts with their status.
    """
    list_display  = [
        'reference_id', 'device', 'package',
        'phone_number', 'amount', 'provider',
        'status', 'created_at'
    ]
    list_filter   = ['status', 'provider']
    search_fields = [
        'reference_id', 'phone_number', 'momo_txn_id'
    ]
    ordering      = ['-created_at']


@admin.register(Withdrawal)
class WithdrawalAdmin(admin.ModelAdmin):
    """
    Admin configuration for withdrawal requests.
    Shows all withdrawal requests with their status.
    """
    list_display  = [
        'amount', 'mobile_number', 'status',
        'verified', 'completed_at', 'created_at'
    ]
    list_filter   = ['status', 'verified']
    search_fields = ['mobile_number', 'reference']
    ordering      = ['-created_at']


@admin.register(VoucherAgent)
class VoucherAgentAdmin(admin.ModelAdmin):
    """
    Admin configuration for voucher agents/resellers.
    Shows all registered agents with their commission info.
    """
    list_display  = [
        'name', 'phone', 'location',
        'commission_type', 'commission_value',
        'status', 'created_at'
    ]
    list_filter   = ['status', 'commission_type']
    search_fields = ['name', 'phone', 'location']
    ordering      = ['-created_at']


@admin.register(Voucher)
class VoucherAdmin(admin.ModelAdmin):
    """
    Admin configuration for voucher codes.
    Shows all generated vouchers with their status.
    """
    list_display  = [
        'code', 'package', 'status',
        'sale_type', 'agent', 'price_sold',
        'used_at', 'created_at'
    ]
    list_filter   = ['status', 'sale_type', 'is_giveaway']
    search_fields = ['code', 'batch_reference']
    ordering      = ['-created_at']