from django.db import router
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from django.db.models import Sum, Count
import json

from network.models import MikroTikRouter,RouterCommand
from network.mikrotik import (
    grant_internet_access,
    revoke_internet_access,
    is_router_reachable,
    get_router_stats,
    reboot_router,
)


@login_required
def router_health(request, router_id):
    """
    Returns real-time health data for a specific router.
    Called by dashboard JavaScript every 30 seconds.
    """
    try:
        router    = get_object_or_404(MikroTikRouter, id=router_id)
        reachable = is_router_reachable(router.connection_address)

        if reachable:
            router.status    = 'online'
            router.last_seen = timezone.now()
        else:
            router.status = 'offline'

        router.save()

        return JsonResponse({
            'status'      : router.status,
            'cpu_usage'   : router.cpu_display,
            'memory_usage': router.memory_display,
            'last_seen'   : router.last_seen.strftime('%Y-%m-%d %H:%M:%S')
                            if router.last_seen else 'Never',
            'is_online'   : router.is_online,
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=404)


@login_required
def router_detail(request, router_id):
    """
    Per-router detail page.
    Shows live stats, active sessions, revenue
    and remote management controls for one router.
    """
    from portal.models import WiFiSession
    from payments.models import Order

    router = get_object_or_404(MikroTikRouter, id=router_id)

    now       = timezone.now()
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    # ── Active sessions on this router ────────────────
    active_sessions = WiFiSession.objects.filter(
        router=router,
        status='active',
        expiry_time__gt=now
    ).select_related('device', 'package').order_by('expiry_time')

    # ── Revenue from this router ───────────────────────
    today_revenue = Order.objects.filter(
        device__last_router=router,
        status='success',
        created_at__gte=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    week_revenue = Order.objects.filter(
        device__last_router=router,
        status='success',
        created_at__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0

    month_revenue = Order.objects.filter(
        device__last_router=router,
        status='success',
        created_at__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_revenue = Order.objects.filter(
        device__last_router=router,
        status='success',
    ).aggregate(total=Sum('amount'))['total'] or 0

    # ── Session stats for this router ─────────────────
    today_sessions = WiFiSession.objects.filter(
        router=router,
        created_at__gte=today
    ).count()

    total_sessions = WiFiSession.objects.filter(
        router=router
    ).count()

    # ── Last 7 days chart data ─────────────────────────
    daily_revenue = []
    daily_users   = []
    day_labels    = []

    for i in range(6, -1, -1):
        day       = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)

        rev = Order.objects.filter(
            device__last_router=router,
            status='success',
            created_at__gte=day_start,
            created_at__lt=day_end
        ).aggregate(total=Sum('amount'))['total'] or 0

        users = WiFiSession.objects.filter(
            router=router,
            created_at__gte=day_start,
            created_at__lt=day_end
        ).count()

        daily_revenue.append(float(rev))
        daily_users.append(users)

        if i == 0:
            day_labels.append('Today')
        elif i == 1:
            day_labels.append('Yesterday')
        else:
            day_labels.append(day.strftime('%a %d'))

    import json
    return render(request, 'dashboard/router_detail.html', {
        'router'        : router,
        'active_sessions': active_sessions,
        'today_revenue' : today_revenue,
        'week_revenue'  : week_revenue,
        'month_revenue' : month_revenue,
        'total_revenue' : total_revenue,
        'today_sessions': today_sessions,
        'total_sessions': total_sessions,
        'daily_revenue' : json.dumps(daily_revenue),
        'daily_users'   : json.dumps(daily_users),
        'day_labels'    : json.dumps(day_labels),
        'now'           : now,
    })

@login_required
def router_reboot(request, router_id):
    """
    Queues a reboot command for the router.
    Router executes it on its next poll cycle.
    Only accepts POST for security.
    """
    router = get_object_or_404(MikroTikRouter, id=router_id)

    if request.method == 'POST':
        RouterCommand.objects.create(
            router      = router,
            action      = 'reboot',
            mac_address = '',
            ip_address  = '',
        )
        return JsonResponse({
            'status' : 'success',
            'message': f'Reboot command queued for {router.identity}. It will reboot within a few seconds.'
        })

    return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

@login_required
def router_refresh_stats(request, router_id):
    """
    Fetches fresh CPU and memory stats from router.
    Called by dashboard Refresh button.
    Returns JSON for live update without page reload.
    """
    router = get_object_or_404(MikroTikRouter, id=router_id)
    stats  = get_router_stats(router.connection_address)

    if stats:
        router.cpu_usage    = stats.get('cpu', 0)
        router.memory_usage = stats.get('memory', 0)
        router.status       = 'online'
        router.last_seen    = timezone.now()
        router.save()
        return JsonResponse({
            'status' : 'success',
            'cpu'    : router.cpu_usage,
            'memory' : router.memory_usage,
        })

    router.status = 'offline'
    router.save()
    return JsonResponse({'status': 'offline', 'cpu': 0, 'memory': 0})


@login_required
def grant_access(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    mac_address = request.POST.get('mac_address')
    ip_address  = request.POST.get('ip_address')

    if not all([mac_address, ip_address]):
        return JsonResponse({'status': 'error', 'message': 'MAC and IP required.'}, status=400)

    success = grant_internet_access(mac_address=mac_address, ip_address=ip_address)

    if success:
        return JsonResponse({'status': 'success', 'message': f'Access granted to {mac_address}'})
    return JsonResponse({'status': 'error', 'message': 'Failed. Check router connection.'})


@login_required
def revoke_access(request):
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    mac_address = request.POST.get('mac_address')
    ip_address  = request.POST.get('ip_address')

    if not all([mac_address, ip_address]):
        return JsonResponse({'status': 'error', 'message': 'MAC and IP required.'}, status=400)

    success = revoke_internet_access(mac_address=mac_address, ip_address=ip_address)

    if success:
        return JsonResponse({'status': 'success', 'message': f'Access revoked for {mac_address}'})
    return JsonResponse({'status': 'error', 'message': 'Failed. Check router connection.'})


@login_required
def check_router_status(request):
    routers = MikroTikRouter.objects.all()
    results = []

    for router in routers:
        reachable     = is_router_reachable(router.connection_address)
        old_status    = router.status
        router.status = 'online' if reachable else 'offline'

        if reachable:
            router.last_seen = timezone.now()

        router.save()

        results.append({
            'id'      : router.id,
            'identity': router.identity,
            'status'  : router.status,
            'changed' : old_status != router.status,
            'last_seen': router.last_seen.strftime('%Y-%m-%d %H:%M:%S')
                         if router.last_seen else 'Never',
        })

    return JsonResponse({
        'routers'      : results,
        'total'        : len(results),
        'online_count' : sum(1 for r in results if r['status'] == 'online'),
        'offline_count': sum(1 for r in results if r['status'] == 'offline'),
    })



@csrf_exempt
def register_router(request):
    """
    Called automatically by the MikroTik setup script.
    Creates or updates a router record in Django.
    No authentication needed — called from MikroTik terminal.
    Matches by identity — safe to run multiple times.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON'}, status=400)

    # ── Extract fields from script payload ─────────────
    identity      = data.get('identity', '').strip()
    location      = data.get('location', '').strip()
    ip_address    = data.get('ip_address', '').strip()
    public_key    = data.get('public_key', '').strip()
    gateway_ip    = data.get('gateway_ip', '192.168.88.1').strip()
    api_username  = data.get('api_username', 'admin').strip()
    api_password  = data.get('api_password', '').strip()
    api_port      = int(data.get('api_port', 8728))
    connection_type = data.get('connection_type', 'wireguard').strip()

    if not identity:
        return JsonResponse({'status': 'error', 'message': 'identity is required'}, status=400)

    # ── Create or update router record ─────────────────
    # Uses identity as unique key — safe to re-run script
    router, created = MikroTikRouter.objects.update_or_create(
        identity=identity,
        defaults={
            'location'           : location,
            'wireguard_tunnel_ip': ip_address,
            'gateway_ip'         : gateway_ip,
            'connection_type'    : connection_type,
            'api_username'       : api_username,
            'api_port'           : api_port,
            'status'             : 'pending',
        }
    )

    # Only update password if provided
    if api_password:
        router.api_password = api_password
        router.save()

    action = 'created' if created else 'updated'

    print(f"\n{'='*50}")
    print(f"🔌 ROUTER {action.upper()}: {identity}")
    print(f"Location  : {location}")
    print(f"Tunnel IP : {ip_address}")
    print(f"Public Key: {public_key}")
    print(f"{'='*50}\n")

    return JsonResponse({
        'status' : 'success',
        'action' : action,
        'message': f'Router {identity} {action} successfully.',
        'router_id': router.id,
    })

@csrf_exempt
def get_commands(request, router_identity):
    """
    Called by MikroTik router every 5 seconds.
    Returns a RouterOS-executable script with pending commands.
    Router downloads and runs it directly.
    Looks up router by identity instead of numeric ID so the
    auto-provisioning script is fully self-contained.
    """
    if request.method != 'GET':
        return JsonResponse({'status': 'error'}, status=405)

    from django.http import HttpResponse

    try:
        router = MikroTikRouter.objects.get(identity=router_identity)
    except MikroTikRouter.DoesNotExist:
        return HttpResponse('# Router not registered\r\n', content_type='text/plain')

    # Update last_seen on every poll — used by health check
    # This marks WireGuard/direct routers as online when they poll
    router.last_seen = timezone.now()
    router.status    = 'online'
    router.save()

    commands = RouterCommand.objects.filter(
        router=router,
        status='pending'
    ).order_by('created_at')

    if not commands.exists():
        return HttpResponse('# No commands\r\n', content_type='text/plain')

    base_url = 'https://kevidtechhotspot.com'
    lines    = []

    for cmd in commands:
        mac = cmd.mac_address

        if cmd.action == 'grant':
            lines.append(f':do {{ /ip hotspot ip-binding remove [find mac-address="{mac}"] }} on-error={{}}')
            lines.append(f':do {{ /ip hotspot ip-binding add mac-address="{mac}" type=bypassed comment="WiFiPortal_{mac}" }} on-error={{}}')
            lines.append(f':do {{ /ip hotspot active remove [find mac-address="{mac}"] }} on-error={{}}')

        elif cmd.action == 'revoke':
            lines.append(f':do {{ /ip hotspot ip-binding remove [find mac-address="{mac}"] }} on-error={{}}')
            lines.append(f':do {{ /ip hotspot active remove [find mac-address="{mac}"] }} on-error={{}}')

        elif cmd.action == 'block':
            lines.append(f':do {{ /ip hotspot ip-binding remove [find mac-address="{mac}"] }} on-error={{}}')
            lines.append(f':do {{ /ip hotspot ip-binding add mac-address="{mac}" type=blocked comment="WiFiPortal_Blocked_{mac}" }} on-error={{}}')

        elif cmd.action == 'unblock':
            lines.append(f':do {{ /ip hotspot ip-binding remove [find mac-address="{mac}" type=blocked] }} on-error={{}}')

        elif cmd.action == 'reboot':
            # Confirm execution BEFORE rebooting since the router
            # won't survive long enough to confirm afterward
            lines.append(
                f'/tool fetch url="{base_url}/network/command/{cmd.id}/confirm/" '
                f'http-method=post '
                f'http-header-field="Content-Type: application/json" '
                f'http-data="{{\\\"success\\\":true}}" '
                f'output=none'
            )
            lines.append(':do { /system reboot } on-error={}')
            continue

        # Confirm command executed
        lines.append(
            f'/tool fetch url="{base_url}/network/command/{cmd.id}/confirm/" '
            f'http-method=post '
            f'http-header-field="Content-Type: application/json" '
            f'http-data="{{\\\"success\\\":true}}" '
            f'output=none'
        )

    script = '\r\n'.join(lines) + '\r\n'
    return HttpResponse(script, content_type='text/plain')





@csrf_exempt
def confirm_command(request, command_id):
    """
    Called by MikroTik after executing a command.
    Marks command as executed or failed.
    """
    if request.method != 'POST':
        return JsonResponse({'status': 'error'}, status=405)

    try:
        data    = json.loads(request.body)
        command = RouterCommand.objects.get(id=command_id)

        if data.get('success'):
            command.status      = 'executed'
            command.executed_at = timezone.now()
        else:
            command.status = 'failed'
            command.error  = data.get('error', 'Unknown error')

        command.save()
        return JsonResponse({'status': 'ok'})

    except RouterCommand.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Command not found'}, status=404)
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)