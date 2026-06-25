from django.contrib import admin
from .models import (
    Expense, Lead, Equipment,
    Advertisement, Message, Feedback
)


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    """
    Admin configuration for business expenses.
    Shows all recorded expenses with their details.
    """
    list_display  = [
        'name', 'expense_type', 'amount',
        'date', 'payment_method', 'vendor',
        'created_at'
    ]
    list_filter   = ['payment_method', 'expense_type']
    search_fields = ['name', 'vendor', 'description']
    ordering      = ['-date', '-created_at']


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    """
    Admin configuration for leads/potential customers.
    Shows all leads with their pipeline status.
    """
    list_display  = [
        'full_name', 'phone_number', 'status',
        'source', 'interested_package',
        'assigned_to', 'created_at'
    ]
    list_filter   = ['status', 'source']
    search_fields = [
        'full_name', 'phone_number',
        'email', 'address'
    ]
    ordering      = ['-created_at']


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    """
    Admin configuration for physical equipment/assets.
    Shows all equipment with their status and location.
    """
    list_display  = [
        'name', 'equipment_type', 'model',
        'serial_number', 'status',
        'location', 'purchase_price',
        'created_at'
    ]
    list_filter   = ['equipment_type', 'status']
    search_fields = [
        'name', 'model', 'serial_number',
        'location', 'vendor'
    ]
    ordering      = ['-created_at']


@admin.register(Advertisement)
class AdvertisementAdmin(admin.ModelAdmin):
    """
    Admin configuration for portal advertisements.
    Shows all ads with their active status and priority.
    """
    list_display  = [
        'title', 'ad_type', 'is_active',
        'priority', 'total_impressions',
        'start_date', 'end_date',
        'created_at'
    ]
    list_filter   = ['ad_type', 'is_active']
    search_fields = ['title', 'description']
    ordering      = ['-priority', 'weight']


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """
    Admin configuration for SMS and WhatsApp messages.
    Shows all sent messages with their delivery status.
    """
    list_display  = [
        'channel', 'phone_number', 'status',
        'customer', 'sent_at', 'created_at'
    ]
    list_filter   = ['channel', 'status']
    search_fields = ['phone_number', 'message']
    ordering      = ['-created_at']


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    """
    Admin configuration for customer feedback.
    Shows all ratings with their comments.
    """
    list_display  = [
        'rating', 'device', 'customer',
        'session', 'created_at'
    ]
    list_filter   = ['rating']
    search_fields = [
        'device__mac_address',
        'comment'
    ]
    ordering      = ['-created_at']