from django.contrib import admin
from .models import MikroTikRouter


@admin.register(MikroTikRouter)
class MikroTikRouterAdmin(admin.ModelAdmin):
    """
    Admin configuration for MikroTik routers.
    Shows all connected routers with their
    health status and connection details.
    """
    list_display  = [
        'identity', 'connection_type',
        'ip_address', 'status',
        'cpu_usage', 'memory_usage',
        'hotspot_enabled', 'last_seen',
        'created_at'
    ]
    list_filter   = [
        'status', 'connection_type',
        'hotspot_enabled', 'has_wireless'
    ]
    search_fields = [
        'identity', 'ip_address',
        'wireguard_tunnel_ip'
    ]
    ordering      = ['identity']

    # Show these fields as read-only in the admin
    # since they are updated automatically by Celery
    readonly_fields = [
        'cpu_usage', 'memory_usage',
        'last_seen', 'status'
    ]