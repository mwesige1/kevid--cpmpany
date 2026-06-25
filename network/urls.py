from django.urls import path
from . import views

app_name = 'network'

urlpatterns = [

    # ── Router Detail ──────────────────────────────────
    # Per-router management page with stats and sessions
    path(
        'router/<int:router_id>/',
        views.router_detail,
        name='router_detail'
    ),

    # ── Router Health ──────────────────────────────────
    # Returns real-time health data for a specific router
    path(
        'router/<int:router_id>/health/',
        views.router_health,
        name='router_health'
    ),

    # Refresh CPU and memory stats from router
    path(
        'router/<int:router_id>/refresh/',
        views.router_refresh_stats,
        name='router_refresh'
    ),

    # ── Remote Reboot ──────────────────────────────────
    # Reboots a specific router remotely via WireGuard
    path(
        'router/<int:router_id>/reboot/',
        views.router_reboot,
        name='router_reboot'
    ),

    # ── Router Status ──────────────────────────────────
    # Check status of all registered routers
    path(
        'routers/status/',
        views.check_router_status,
        name='check_router_status'
    ),

    # ── Access Control ─────────────────────────────────
    # Manually grant internet access to a device
    path(
        'access/grant/',
        views.grant_access,
        name='grant_access'
    ),

    # Manually revoke internet access from a device
    path(
        'access/revoke/',
        views.revoke_access,
        name='revoke_access'
    ),

    # ── Auto Registration ──────────────────────────────
    # Called by MikroTik setup script to self-register
    path(
        'register-router/',
        views.register_router,
        name='register_router'
    ),
    # ── Router Command Queue ───────────────────────────
    # MikroTik polls this for pending commands
    path(
    'router/<str:router_identity>/commands/',
    views.get_commands,
    name='get_commands'
    ),

    # MikroTik confirms command execution
    path(
        'command/<int:command_id>/confirm/',
        views.confirm_command,
        name='confirm_command'
    ),
]