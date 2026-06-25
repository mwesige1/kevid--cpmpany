from django.contrib import admin
from .models import Package, Device, Customer, WiFiSession


@admin.register(Package)
class PackageAdmin(admin.ModelAdmin):
    """Admin configuration for WiFi packages."""
    list_display  = [
        'name', 'duration', 'duration_unit',
        'price', 'upload_speed', 'download_speed',
        'status', 'is_featured'
    ]
    list_filter   = ['status', 'is_featured', 'is_free_trial', 'duration_unit']
    search_fields = ['name', 'description']
    ordering      = ['display_order', 'price']


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin configuration for connected devices."""
    list_display  = [
        'mac_address', 'phone_number',
        'total_spent', 'is_blocked',
        'first_seen', 'last_seen'
    ]
    list_filter   = ['is_blocked']
    search_fields = ['mac_address', 'phone_number']


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Admin configuration for registered customers."""
    list_display  = [
        'full_name', 'phone_number', 'email',
        'status', 'package', 'total_spent',
        'created_at'
    ]
    list_filter   = ['status']
    search_fields = ['first_name', 'last_name', 'phone_number', 'email']
    ordering      = ['-created_at']


@admin.register(WiFiSession)
class WiFiSessionAdmin(admin.ModelAdmin):
    """Admin configuration for WiFi sessions."""
    list_display  = [
        'device', 'package', 'ip_address',
        'start_time', 'expiry_time', 'status'
    ]
    list_filter   = ['status']
    search_fields = ['device__mac_address', 'ip_address']
    ordering      = ['-created_at']