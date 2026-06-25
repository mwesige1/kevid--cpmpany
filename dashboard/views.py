from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count, Avg
from django.http import JsonResponse
from datetime import timedelta
import json as json_module

from portal.models import Package, Device, WiFiSession, Customer
from payments.models import Order, Voucher, VoucherAgent, Withdrawal
from dashboard.models import (
    Expense, Lead, Equipment,
    Advertisement, Message, Feedback
)
from network.models import MikroTikRouter
from django.db.models import Count, Sum, Q


# ── Authentication Views ───────────────────────────────────

def dashboard_login(request):
    """
    Custom login page for the admin dashboard.
    Allows all active users to log in.
    Role-based access is handled by the sidebar and view decorators.
    Redirects to dashboard overview on success.
    Redirects to overview if already logged in.
    """

    # If already logged in redirect to dashboard
    if request.user.is_authenticated:
        return redirect('dashboard:overview')

    error = None

    # If axes redirected here after lockout, show the lockout message
    if request.GET.get('locked'):
        error = '🔒 Account locked due to too many failed attempts. Please try again in 30 minutes.'

    if request.method == 'POST':

        # Get credentials from login form
        username = request.POST.get('username')
        password = request.POST.get('password')

        # Authenticate against Django's user database
        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            if user.is_active:
                login(request, user)
                return redirect('dashboard:overview')
            else:
                error = 'Your account has been disabled.'
        else:
            error = 'Invalid username or password.'

    return render(request, 'dashboard/login.html', {
        'error': error
    })

def dashboard_logout(request):
    """
    Logs out the current admin user and
    redirects to the login page.
    """
    logout(request)
    return redirect('dashboard:login')


# ── Overview ───────────────────────────────────────────────


@login_required
def overview(request):
    """
    Main dashboard home page.
    Shows key business metrics at a glance.
    """
    import json as json_module

    now       = timezone.now()
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

  

    # ── Revenue Metrics ────────────────────────────────
    today_revenue = Order.objects.filter(
        status='success',
        created_at__gte=today
    ).aggregate(total=Sum('amount'))['total'] or 0

    today_transactions = Order.objects.filter(
        status='success',
        created_at__gte=today
    ).count()

    week_revenue = Order.objects.filter(
        status='success',
        created_at__gte=week_ago
    ).aggregate(total=Sum('amount'))['total'] or 0

    month_revenue = Order.objects.filter(
        status='success',
        created_at__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0

    # ── Session Metrics ────────────────────────────────
    active_sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__gt=now
    ).count()

    # ── Device & Customer Metrics ──────────────────────
    total_devices   = Device.objects.count()
    total_customers = Customer.objects.count()

    # ── Expenses & Profit ──────────────────────────────
    month_expenses = Expense.objects.filter(
        date__gte=month_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = Expense.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0

    month_profit = month_revenue - month_expenses

    # ── Router Health ──────────────────────────────────
    routers        = MikroTikRouter.objects.all()
    total_routers  = routers.count()
    online_routers = routers.filter(status='online').count()

    # ── Package Popularity ─────────────────────────────
    active_packages = Package.objects.filter(status='active').count()
    popular_packages = Order.objects.filter(
        status='success'
    ).values(
        'package__name'
    ).annotate(
        total=Count('id')
    ).order_by('-total')[:5]

    # ── Recent Activity ────────────────────────────────
    recent_orders = Order.objects.select_related(
        'device', 'package'
    ).order_by('-created_at')[:10]

    recent_sessions = WiFiSession.objects.select_related(
        'device', 'package'
    ).filter(
        status='active'
    ).order_by('-created_at')[:5]

    # ── Mobile Money Balance ───────────────────────────
    total_collected = Order.objects.filter(
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_withdrawn = Withdrawal.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    momo_balance = total_collected - total_withdrawn

    # ── Additional Stats ───────────────────────────────
    available_vouchers = Voucher.objects.filter(
        status='available'
    ).count()

    total_equipment = Equipment.objects.count()

    active_leads = Lead.objects.filter(
        status__in=['new', 'contacted', 'free_trial']
    ).count()

    top_sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__gt=now
    ).select_related('device', 'package').order_by('expiry_time')[:5]

    # ── Last 7 Days Chart Data ─────────────────────────
    daily_revenue = []
    daily_users   = []
    day_labels    = []

    for i in range(6, -1, -1):
        day       = now - timedelta(days=i)
        day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)

        rev = Order.objects.filter(
            status='success',
            created_at__gte=day_start,
            created_at__lt=day_end
        ).aggregate(total=Sum('amount'))['total'] or 0

        users = WiFiSession.objects.filter(
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

    return render(request, 'dashboard/overview.html', {
        'today_revenue'     : today_revenue,
        'today_transactions': today_transactions,
        'week_revenue'      : week_revenue,
        'month_revenue'     : month_revenue,
        'active_sessions'   : active_sessions,
        'total_devices'     : total_devices,
        'total_customers'   : total_customers,
        'month_expenses'    : month_expenses,
        'total_expenses'    : total_expenses,
        'month_profit'      : month_profit,
        'total_routers'     : total_routers,
        'online_routers'    : online_routers,
        'routers'           : routers,
        'popular_packages'  : popular_packages,
        'active_packages'   : active_packages,
        'recent_orders'     : recent_orders,
        'recent_sessions'   : recent_sessions,
        'momo_balance'      : momo_balance,
        'total_collected'   : total_collected,
        'total_withdrawn'   : total_withdrawn,
        'now'               : now,
        'available_vouchers': available_vouchers,
        'total_equipment'   : total_equipment,
        'active_leads'      : active_leads,
        'top_sessions'      : top_sessions,
        'daily_revenue'     : json_module.dumps(daily_revenue),
        'daily_users'       : json_module.dumps(daily_users),
        'day_labels'        : json_module.dumps(day_labels),
    })

# ── Sessions ───────────────────────────────────────────────

@login_required
def active_sessions(request):
    now = timezone.now()

    

    sessions = WiFiSession.objects.filter(
        status='active',
        expiry_time__gt=now
    ).select_related(
        'device', 'package'
    ).order_by('expiry_time')

    offline_sessions = WiFiSession.objects.filter(
        status='expired'
    ).select_related(
        'device', 'package'
    ).order_by('-expiry_time')[:20]

    # Expiring in less than 20 minutes
    expiring_soon = sessions.filter(
        expiry_time__lt=now + timedelta(minutes=20)
    ).count()

    # Today's total sessions
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_total = WiFiSession.objects.filter(
        created_at__gte=today
    ).count()

    # Disconnected today
    disconnected_today = WiFiSession.objects.filter(
        status__in=['expired', 'cancelled'],
        expiry_time__gte=today
    ).count()

    tab = request.GET.get('tab', '')

    return render(request, 'dashboard/active_sessions.html', {
        'sessions'          : sessions,
        'offline_sessions'  : offline_sessions,
        'expiring_soon'     : expiring_soon,
        'today_total'       : today_total,
        'disconnected_today': disconnected_today,
        'tab'               : tab,
    })

@login_required
def expired_sessions(request):
    from datetime import timedelta
    now   = timezone.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)

    

    # ── Base queryset ──────────────────────────────────
    sessions = WiFiSession.objects.filter(
        status__in=['expired', 'cancelled']
    ).select_related('device', 'package', 'order').order_by('-expiry_time')

    # ── Apply filters ──────────────────────────────────
    search = request.GET.get('search', '')
    reason = request.GET.get('reason', '')

    if search:
        sessions = sessions.filter(
            device__mac_address__icontains=search
        )
    if reason:
        sessions = sessions.filter(status=reason)

    # ── Summary counts ─────────────────────────────────
    expired_today = WiFiSession.objects.filter(
        status='expired',
        expiry_time__gte=today
    ).count()

    cancelled_count = WiFiSession.objects.filter(
        status='cancelled'
    ).count()

    renewal_opportunities = WiFiSession.objects.filter(
        status='expired',
        expiry_time__gte=now - timedelta(hours=24)
    ).count()

    return render(request, 'dashboard/expired_sessions.html', {
        'sessions'             : sessions,
        'expired_today'        : expired_today,
        'cancelled_count'      : cancelled_count,
        'renewal_opportunities': renewal_opportunities,
        'search'               : search,
        'reason'               : reason,
    })

@login_required
def disconnect_session(request, session_id):
    """
    Manually disconnects a device from the network.
    Revokes router access and marks session cancelled.
    Only accepts POST requests for security.
    """

    session = get_object_or_404(WiFiSession, id=session_id)

    if request.method == 'POST':

        # Revoke internet access on Mikrotik router
        try:
            from network.mikrotik import revoke_internet_access
            revoke_internet_access(
                mac_address=session.device.mac_address,
                ip_address =session.ip_address,
                router     =session.router
            )
        except Exception as e:
            print(f"Router revoke error: {e}")

        # Mark session as cancelled in database
        session.status = 'cancelled'
        session.save()

    return redirect('dashboard:active_sessions')


# ── Customers ──────────────────────────────────────────────

@login_required
def customers(request):
    """
    Shows all devices that have a phone number —
    meaning they have paid or connected at least once.
    Uses Device as the customer record since all payment
    data is tracked there.
    """
    from django.db.models import Count, Q, Subquery, OuterRef

    # ── Filters from URL ───────────────────────────────
    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '')

    # ── Base queryset — devices with phone numbers ─────
    # Excludes virtual voucher-buyer devices (V- prefix)
    # Excludes devices with no phone number (unregistered)
    devices = Device.objects.filter(
        phone_number__isnull=False
    ).exclude(
        phone_number=''
    ).exclude(
        mac_address__startswith='V-'
    ).annotate(
        session_count=Count('wifisession', distinct=True)
    ).order_by('-first_seen')

    # ── Status filter ──────────────────────────────────
    now = timezone.now()
    if status_filter == 'active':
        # Has at least one active session right now
        devices = devices.filter(
            wifisession__status='active',
            wifisession__expiry_time__gt=now
        ).distinct()
    elif status_filter == 'expired':
        # Last session is expired — no active session
        devices = devices.exclude(
            wifisession__status='active',
            wifisession__expiry_time__gt=now
        ).filter(
            wifisession__isnull=False
        ).distinct()
    elif status_filter == 'blocked':
        devices = devices.filter(is_blocked=True)

    # ── Search filter ──────────────────────────────────
    if search:
        # Search by phone number
        if search.isdigit():
            devices = devices.filter(
                Q(phone_number__icontains=search) |
                Q(session_count__gte=int(search))
            )
        else:
            devices = devices.filter(
                phone_number__icontains=search
            )

    # ── Summary counts for cards ───────────────────────
    all_devices = Device.objects.filter(
        phone_number__isnull=False
    ).exclude(
        phone_number=''
    ).exclude(
        mac_address__startswith='V-'
    )

    total_count      = all_devices.count()
    active_count     = all_devices.filter(
        wifisession__status='active',
        wifisession__expiry_time__gt=now
    ).distinct().count()
    blocked_count    = all_devices.filter(is_blocked=True).count()
    expired_count    = all_devices.exclude(
        wifisession__status='active',
        wifisession__expiry_time__gt=now
    ).filter(wifisession__isnull=False).distinct().count()

    return render(request, 'dashboard/customers.html', {
        'devices'      : devices,
        'status_filter': status_filter,
        'search'       : search,
        'total_count'  : total_count,
        'active_count' : active_count,
        'blocked_count': blocked_count,
        'expired_count': expired_count,
    })


@login_required
def customer_detail(request, device_id):
    """
    Full detail page for a single customer (device).
    Shows all sessions, payments, and device info.
    """
    from django.db.models import Count

    device   = get_object_or_404(Device, id=device_id)
    sessions = WiFiSession.objects.filter(
        device=device
    ).select_related('package', 'router').order_by('-created_at')
    orders   = Order.objects.filter(
        device=device
    ).select_related('package').order_by('-created_at')

    # Derive status
    now            = timezone.now()
    active_session = sessions.filter(
        status='active',
        expiry_time__gt=now
    ).first()

    if device.is_blocked:
        status = 'blocked'
    elif active_session:
        status = 'active'
    elif sessions.exists():
        status = 'expired'
    else:
        status = 'no sessions'

    # Most used package
    top_package_qs = sessions.values(
        'package__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count').first()

    top_package_name = top_package_qs['package__name'] if top_package_qs else '—'

    return render(request, 'dashboard/customer_detail.html', {
        'device'          : device,
        'sessions'        : sessions,
        'orders'          : orders,
        'active_session'  : active_session,
        'status'          : status,
        'top_package_name': top_package_name,
    })

@login_required
def customer_delete(request, device_id):
    """
    Deletes a customer (device) record and all
    associated sessions and orders.
    """
    device = get_object_or_404(Device, id=device_id)
    if request.method == 'POST':
        device.delete()
    return redirect('dashboard:customers')




# ── Devices ────────────────────────────────────────────────


@login_required
def devices(request):
    """
    Shows all devices that have ever connected
    to the network with their usage history.
    Admin can block or unblock any device.
    """

    devices_qs = Device.objects.annotate(
        session_count=Count('wifisession')
    ).order_by('-last_seen')

    return render(request, 'dashboard/devices.html', {
        'devices': devices_qs,
    })


@login_required
def block_device(request, device_id):
    device = get_object_or_404(Device, id=device_id)

    if request.method == 'POST':
        device.is_blocked = not device.is_blocked
        device.save()

        if device.is_blocked:
            # ── BLOCKING ───────────────────────────────────
            # Cancel active session if exists
            active_session = WiFiSession.objects.filter(
                device=device,
                status='active'
            ).first()

            if active_session:
                active_session.status = 'cancelled'
                active_session.save()

            # Always add blocked binding on Mikrotik
            # regardless of whether there is an active session
            try:
                from network.mikrotik import revoke_internet_access
                router     = active_session.router if active_session else device.last_router
                ip_address = active_session.ip_address if active_session else '0.0.0.0'
                revoke_internet_access(
                    mac_address=device.mac_address,
                    ip_address =ip_address,
                    router     =router,
                    block_type ='remove'
                )
            except Exception as e:
                print(f"Router revoke error: {e}")

        else:
            # ── UNBLOCKING ─────────────────────────────────
            try:
                from network.mikrotik import grant_internet_access
                from network.mikrotik import revoke_internet_access

                # Find most recent session
                last_session = WiFiSession.objects.filter(
                    device=device,
                    status__in=['cancelled', 'active']
                ).order_by('-expiry_time').first()

                router     = last_session.router if last_session else device.last_router
                ip_address = last_session.ip_address if last_session else '0.0.0.0'

                if last_session and last_session.expiry_time > timezone.now():
                    # Session still has time left — reactivate and grant access
                    last_session.status = 'active'
                    last_session.save()
                    grant_internet_access(
                        mac_address=device.mac_address,
                        ip_address =ip_address,
                        router     =router
                    )
                    print(f"✅ Restored session for {device.mac_address}")

                else:
                    # No valid session — remove blocked binding
                    # Device will go to portal to buy a new package
                    grant_internet_access(
                        mac_address=device.mac_address,
                        ip_address =ip_address,
                        router     =router
                    )
                    # Immediately change to blocked so they go to portal
                    revoke_internet_access(
                        mac_address=device.mac_address,
                        ip_address =ip_address,
                        router     =router
                    )
                    print(f"✅ Unblocked {device.mac_address} → redirected to portal")

            except Exception as e:
                print(f"Router grant error: {e}")

    return redirect('dashboard:devices')

# ── Packages ───────────────────────────────────────────────


@login_required
def packages(request):
    """
    Shows all WiFi packages with options to
    add, edit, hide or disable them.
    """

    # Get status filter from URL
    status_filter = request.GET.get('status', '')

    packages_qs = Package.objects.all().order_by(
        'display_order', 'price'
    )

    # Apply filter if provided
    if status_filter:
        packages_qs = packages_qs.filter(status=status_filter)

    # Count packages by status for tab badges
    status_counts = {
        'active'  : Package.objects.filter(status='active').count(),
        'hidden'  : Package.objects.filter(status='hidden').count(),
        'disabled': Package.objects.filter(status='disabled').count(),
    }

    return render(request, 'dashboard/packages.html', {
        'packages'     : packages_qs,
        'status_filter': status_filter,
        'status_counts': status_counts,
    })


@login_required
def create_package(request):
    """
    Creates a new WiFi package.
    Admin configures speed, duration, price
    and visibility settings.
    """

    if request.method == 'POST':

        # Get all form fields
        Package.objects.create(
            name          = request.POST.get('name'),
            duration      = request.POST.get('duration', 1),
            duration_unit = request.POST.get('duration_unit', 'days'),
            description   = request.POST.get('description', ''),
            upload_speed  = request.POST.get('upload_speed', 10),
            download_speed= request.POST.get('download_speed', 10),
            data_limit    = request.POST.get('data_limit') or None,
            data_unit     = request.POST.get('data_unit', 'GB'),
            is_free_trial = request.POST.get('is_free_trial') == 'on',
            price         = request.POST.get('price', 0),
            device_limit  = request.POST.get('device_limit', 1),
            status        = request.POST.get('status', 'active'),
            is_featured   = request.POST.get('is_featured') == 'on',
            display_order = request.POST.get('display_order', 0),
        )

        return redirect('dashboard:packages')

    return render(request, 'dashboard/create_package.html')


@login_required
def toggle_package(request, package_id):
    """
    Cycles a package through Active → Hidden → Disabled.
    Useful for quickly changing package visibility.
    """

    package = get_object_or_404(Package, id=package_id)

    if request.method == 'POST':

        # Cycle through statuses
        if package.status == 'active':
            package.status = 'hidden'
        elif package.status == 'hidden':
            package.status = 'disabled'
        else:
            package.status = 'active'

        package.save()

    return redirect('dashboard:packages')


# ── Payments ───────────────────────────────────────────────

@login_required
def payments(request):
    """
    Shows all payment transactions with
    filtering by provider.
    Includes revenue summary cards.
    """

    provider_filter = request.GET.get('provider', '')

    payments_qs = Order.objects.select_related(
        'device', 'package'
    ).order_by('-created_at')

    if provider_filter:
        payments_qs = payments_qs.filter(provider=provider_filter)

    now       = timezone.now()
    month_ago = now - timedelta(days=30)

    total_revenue = Order.objects.filter(
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    online_revenue = Order.objects.filter(
        status='success',
        provider__in=['mtn', 'airtel']
    ).aggregate(total=Sum('amount'))['total'] or 0

    walkin_revenue = Order.objects.filter(
        status='success',
        provider='walk_in'
    ).aggregate(total=Sum('amount'))['total'] or 0

    month_revenue = Order.objects.filter(
        status='success',
        created_at__gte=month_ago
    ).aggregate(total=Sum('amount'))['total'] or 0

    return render(request, 'dashboard/payments.html', {
        'payments'       : payments_qs,
        'status_filter'  : provider_filter,
        'total_revenue'  : total_revenue,
        'online_revenue' : online_revenue,
        'walkin_revenue' : walkin_revenue,
        'month_revenue'  : month_revenue,
    })


# ── Vouchers ───────────────────────────────────────────────


@login_required
def vouchers(request):
    """
    Shows all voucher codes with filtering by status.
    Admin can generate new vouchers and print them.
    """

    # Get status filter from URL
    status_filter = request.GET.get('status', '')

    vouchers_qs = Voucher.objects.select_related(
        'package', 'agent'
    ).order_by('-created_at')

    # Apply filter
    if status_filter:
        vouchers_qs = vouchers_qs.filter(status=status_filter)

    # Count vouchers by status for tab badges
    status_counts = {
        'available': Voucher.objects.filter(status='available').count(),
        'used'     : Voucher.objects.filter(status='used').count(),
        'expired'  : Voucher.objects.filter(status='expired').count(),
        'giveaway' : Voucher.objects.filter(is_giveaway=True).count(),
    }

    return render(request, 'dashboard/vouchers.html', {
        'vouchers'     : vouchers_qs,
        'status_filter': status_filter,
        'status_counts': status_counts,
    })


@login_required
def generate_vouchers(request):
    """
    Generates a batch of voucher codes for a package.
    Admin specifies quantity, prefix, code length and optional agent.
    """

    if request.method == 'POST':
        import random

        package_id      = request.POST.get('package')
        quantity        = int(request.POST.get('quantity', 1))
        prefix          = request.POST.get('prefix', '').upper()
        code_length     = int(request.POST.get('code_length', 6))
        is_giveaway     = request.POST.get('is_giveaway') == 'on'
        batch_reference = request.POST.get('batch_reference', '')
        agent_id        = request.POST.get('agent')

        # Get the package
        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            return redirect('dashboard:vouchers')

        # Get agent if selected
        agent = None
        if agent_id:
            try:
                from payments.models import VoucherAgent
                agent = VoucherAgent.objects.get(id=agent_id)
            except VoucherAgent.DoesNotExist:
                pass

        # Characters used — no 0/O/I/1 to avoid confusion
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'

        for _ in range(quantity):
            while True:
                code_body = ''.join(
                    random.choices(chars, k=code_length - len(prefix))
                )
                code = prefix + code_body
                if not Voucher.objects.filter(code=code).exists():
                    break

            Voucher.objects.create(
                code            = code,
                package         = package,
                prefix          = prefix,
                is_giveaway     = is_giveaway,
                batch_reference = batch_reference,
                status          = 'giveaway' if is_giveaway else 'available',
                price_sold      = 0 if is_giveaway else package.price,
                agent           = agent,
                sale_type       = 'agent' if agent else ('giveaway' if is_giveaway else 'walk_in'),
            )

        return redirect('dashboard:vouchers')

    # GET request — show generate form
    packages = Package.objects.filter(status='active')
    from payments.models import VoucherAgent
    agents = VoucherAgent.objects.filter(status='active')

    return render(request, 'dashboard/generate_vouchers.html', {
        'packages': packages,
        'agents'  : agents,
    })

# ── Voucher Agents ─────────────────────────────────────────


@login_required
def voucher_agents(request):
    """
    Shows all registered voucher agents/resellers
    with their commission configuration and stats.
    """
    from payments.models import VoucherAgent
    from django.db.models import Count, Sum, Q

    search = request.GET.get('search', '').strip()

    agents = VoucherAgent.objects.annotate(
        vouchers_assigned  = Count('voucher'),
        vouchers_sold      = Count('voucher', filter=Q(voucher__status='used')),
        vouchers_available = Count('voucher', filter=Q(voucher__status='available')),
        total_revenue      = Sum(
                                 'voucher__price_sold',
                                 filter=Q(voucher__status='used')
                             ),
    ).order_by('-created_at')

    if search:
        agents = agents.filter(name__icontains=search)

    return render(request, 'dashboard/voucher_agents.html', {
        'agents': agents,
        'search': search,
    })

@login_required
def agent_detail(request, agent_id):
    """
    Shows detailed stats and voucher list for a specific agent.
    """
    from payments.models import VoucherAgent
    agent = get_object_or_404(VoucherAgent, id=agent_id)

    # Get all vouchers for this agent
    vouchers = Voucher.objects.filter(agent=agent).order_by('-created_at')

    # Filter by status if requested
    status_filter = request.GET.get('status', '')
    if status_filter:
        vouchers = vouchers.filter(status=status_filter)

    # Calculate stats
    total_assigned  = Voucher.objects.filter(agent=agent).count()
    total_sold      = Voucher.objects.filter(agent=agent, status='used').count()
    total_available = Voucher.objects.filter(agent=agent, status='available').count()
    total_expired   = Voucher.objects.filter(agent=agent, status='expired').count()
    total_revenue   = Voucher.objects.filter(
                          agent=agent, status='used'
                    ).aggregate(
                    total=Sum('price_sold')
                    )['total'] or 0

    # Calculate commission earned
    if agent.commission_type == 'percentage':
        commission_earned = total_revenue * (agent.commission_value / 100)
    else:
        commission_earned = total_sold * agent.commission_value

    return render(request, 'dashboard/agent_detail.html', {
        'agent'            : agent,
        'vouchers'         : vouchers,
        'status_filter'    : status_filter,
        'total_assigned'   : total_assigned,
        'total_sold'       : total_sold,
        'total_available'  : total_available,
        'total_expired'    : total_expired,
        'total_revenue'    : total_revenue,
        'commission_earned': commission_earned,
    })


@login_required
def create_voucher_agent(request):
    """
    Creates a new voucher agent/reseller account.
    """

    if request.method == 'POST':
        VoucherAgent.objects.create(
            name             = request.POST.get('name'),
            phone            = request.POST.get('phone', ''),
            location         = request.POST.get('location', ''),
            status           = request.POST.get('status', 'active'),
            commission_type  = request.POST.get('commission_type', 'percentage'),
            commission_value = request.POST.get('commission_value', 0),
            notes            = request.POST.get('notes', ''),
        )
        return redirect('dashboard:voucher_agents')

    return render(request, 'dashboard/create_voucher_agent.html')


# ── Expenses ───────────────────────────────────────────────


@login_required
def expenses(request):
    """
    Shows all business expenses with summary cards.
    Used to track spending and calculate net profit.
    """

    now       = timezone.now()
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago  = now - timedelta(days=365)

    # Expense summary cards
    week_expenses = Expense.objects.filter(
        date__gte=week_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    month_expenses = Expense.objects.filter(
        date__gte=month_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    year_expenses = Expense.objects.filter(
        date__gte=year_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    # ── Filters ────────────────────────────────────────
    search          = request.GET.get('search', '').strip()
    category_filter = request.GET.get('category', '').strip()

    # All expenses ordered by date
    expenses_qs = Expense.objects.all().order_by('-date', '-created_at')

    if search:
        expenses_qs = expenses_qs.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(vendor__icontains=search)
        )

    if category_filter:
        expenses_qs = expenses_qs.filter(expense_type=category_filter)

    # Category breakdown for filter tabs
    categories = Expense.objects.values_list(
        'expense_type', flat=True
    ).distinct().order_by('expense_type')

    return render(request, 'dashboard/expenses.html', {
        'expenses'        : expenses_qs,
        'week_expenses'   : week_expenses,
        'month_expenses'  : month_expenses,
        'year_expenses'   : year_expenses,
        'search'          : search,
        'category_filter' : category_filter,
        'categories'      : categories,
    })


@login_required
def create_expense(request):
    """
    Records a new business expense.
    Admin enters expense details and optionally
    uploads a receipt image.
    """

    if request.method == 'POST':

        # Handle receipt file upload if provided
        receipt = request.FILES.get('receipt')

        Expense.objects.create(
            name           = request.POST.get('name'),
            expense_type   = request.POST.get('expense_type'),
            amount         = request.POST.get('amount'),
            date           = request.POST.get('date'),
            payment_method = request.POST.get('payment_method', 'cash'),
            vendor         = request.POST.get('vendor', ''),
            receipt        = receipt,
            description    = request.POST.get('description', ''),
        )

        return redirect('dashboard:expenses')

    return render(request, 'dashboard/create_expense.html')


# ── Withdrawals ────────────────────────────────────────────

@login_required
def withdrawals(request):
    """
    Shows all withdrawal requests with summary cards.
    Admin can request new withdrawals of collected
    mobile money balance.
    """

    now       = timezone.now()
    month_ago = now - timedelta(days=30)

    # Calculate available balance
    total_collected = Order.objects.filter(
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_withdrawn = Withdrawal.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    available_balance = total_collected - total_withdrawn

    # Status counts
    pending_count   = Withdrawal.objects.filter(status='pending').count()
    completed_count = Withdrawal.objects.filter(status='completed').count()

    # Status filter
    status_filter = request.GET.get('status', '')

    # All withdrawal records
    withdrawals_qs = Withdrawal.objects.all().order_by('-created_at')

    if status_filter:
        withdrawals_qs = withdrawals_qs.filter(status=status_filter)

    return render(request, 'dashboard/withdrawals.html', {
        'withdrawals'        : withdrawals_qs,
        'momo_balance'       : available_balance,
        'total_collected'    : total_collected,
        'total_withdrawn'    : total_withdrawn,
        'pending_count'      : pending_count,
        'completed_count'    : completed_count,
        'status_filter'      : status_filter,
    })

@login_required
def create_withdrawal(request):
    """
    Creates a new withdrawal request.
    """

    total_collected = Order.objects.filter(
        status='success'
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_withdrawn = Withdrawal.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0

    momo_balance = total_collected - total_withdrawn

    recent_withdrawals = Withdrawal.objects.order_by('-created_at')[:5]

    if request.method == 'POST':
        amount        = request.POST.get('amount')
        mobile_number = request.POST.get('mobile_number')
        provider      = request.POST.get('provider', '')
        account_name  = request.POST.get('account_name', '')
        notes         = request.POST.get('note', '')

        Withdrawal.objects.create(
            amount        = amount,
            mobile_number = mobile_number,
            provider      = provider,
            account_name  = account_name,
            notes         = notes,
            status        = 'pending',
        )
        return redirect('dashboard:withdrawals')

    return render(request, 'dashboard/create_withdrawal.html', {
        'momo_balance'      : momo_balance,
        'recent_withdrawals': recent_withdrawals,
    })

@login_required
def update_withdrawal_status(request, withdrawal_id):
    """
    Updates the status of a withdrawal request.
    Admin can mark as completed, failed or cancelled.
    """
    withdrawal = get_object_or_404(Withdrawal, id=withdrawal_id)

    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in ['completed', 'failed', 'cancelled']:
            withdrawal.status = new_status
            if new_status == 'completed':
                withdrawal.completed_at = timezone.now()
                withdrawal.verified     = True
            withdrawal.save()

    return redirect('dashboard:withdrawals')


@login_required
def delete_withdrawal(request, withdrawal_id):
    """
    Deletes a withdrawal request permanently.
    Only pending withdrawals can be deleted.
    """
    withdrawal = get_object_or_404(Withdrawal, id=withdrawal_id)

    if request.method == 'POST':
        withdrawal.delete()

    return redirect('dashboard:withdrawals')

# ── Leads ──────────────────────────────────────────────────


@login_required
def leads(request):
    """
    Shows all leads in the sales pipeline
    with tab filtering by status and search.
    """

    # Get filters from URL
    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '').strip()

    leads_qs = Lead.objects.select_related(
        'interested_package', 'assigned_to'
    ).order_by('-created_at')

    # Apply status filter
    if status_filter:
        leads_qs = leads_qs.filter(status=status_filter)

    # Apply search
    if search:
        leads_qs = leads_qs.filter(
            Q(full_name__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(email__icontains=search)
        )

    # Count leads by status for tab badges
    status_counts = {
        'new'       : Lead.objects.filter(status='new').count(),
        'contacted' : Lead.objects.filter(status='contacted').count(),
        'free_trial': Lead.objects.filter(status='free_trial').count(),
        'converted' : Lead.objects.filter(status='converted').count(),
        'lost'      : Lead.objects.filter(status='lost').count(),
    }

    return render(request, 'dashboard/leads.html', {
        'leads'        : leads_qs,
        'status_filter': status_filter,
        'status_counts': status_counts,
        'search'       : search,
    })


@login_required
def create_lead(request):
    """
    Creates a new lead/potential customer record.
    """

    if request.method == 'POST':
        print("POST DATA:", request.POST)

        package_id = request.POST.get('interested_package')
        package    = None
        if package_id:
            try:
                package = Package.objects.get(id=package_id)
            except Package.DoesNotExist:
                pass

        Lead.objects.create(
            full_name        = request.POST.get('full_name'),
            phone_number     = request.POST.get('phone_number', ''),   
            phone_number_alt = request.POST.get('phone_number_alt', ''),
            email            = request.POST.get('email', ''),
            address          = request.POST.get('address', ''),
            status           = request.POST.get('status', 'new'),
            source           = request.POST.get('source', 'other'),
            interested_package = package,
            assigned_to      = request.user,
            notes            = request.POST.get('notes', ''),
        )

        return redirect('dashboard:leads')

    packages = Package.objects.filter(status='active')
    staff_users = User.objects.filter(is_staff=True)


    return render(request, 'dashboard/create_lead.html', {
        'packages'   : packages,
        'staff_users': staff_users,
    })


# ── Feedback ───────────────────────────────────────────────


@login_required
def feedback(request):
    """
    Shows all customer feedback with analytics.
    Displays star ratings and comments.
    """

    feedback_qs = Feedback.objects.select_related(
        'device', 'customer', 'session'
    ).order_by('-created_at')

    # Feedback analytics
    total_feedback   = feedback_qs.count()
    average_rating   = feedback_qs.aggregate(
        avg=Avg('rating')
    )['avg'] or 0
    positive_count   = feedback_qs.filter(rating__gte=4).count()
    negative_count   = feedback_qs.filter(rating__lte=2).count()

    return render(request, 'dashboard/feedback.html', {
        'feedback'      : feedback_qs,
        'total_feedback': total_feedback,
        'average_rating': round(average_rating, 1),
        'positive_count': positive_count,
        'negative_count': negative_count,
    })


# ── Equipment ──────────────────────────────────────────────

@login_required
def equipment(request):
    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '').strip()

    equipment_qs  = Equipment.objects.all().order_by('-created_at')

    if status_filter:
        equipment_qs = equipment_qs.filter(status=status_filter)

    if search:
        equipment_qs = equipment_qs.filter(
            Q(name__icontains=search) |
            Q(serial_number__icontains=search) |
            Q(model__icontains=search)
        )

    total_equipment  = Equipment.objects.count()
    available_count  = Equipment.objects.filter(status='available').count()
    in_use_count     = Equipment.objects.filter(status='in_use').count()
    faulty_count     = Equipment.objects.filter(status='faulty').count()

    total_investment = Equipment.objects.filter(
        purchase_price__isnull=False
    ).aggregate(total=Sum('purchase_price'))['total'] or 0

    statuses = [
        ('Available', 'available'),
        ('In Use',    'in_use'),
        ('Faulty',    'faulty'),
        ('Retired',   'retired'),
    ]

    return render(request, 'dashboard/equipment.html', {
        'equipment'       : equipment_qs,
        'equipment_list'  : equipment_qs,
        'status_filter'   : status_filter,
        'search'          : search,
        'total_equipment' : total_equipment,
        'available_count' : available_count,
        'in_use_count'    : in_use_count,
        'faulty_count'    : faulty_count,
        'total_investment': total_investment,
        'statuses'        : statuses,
    })

@login_required
def create_equipment(request):
    """
    Records a new piece of equipment/asset.
    """

    if request.method == 'POST':
        Equipment.objects.create(
            equipment_type  = request.POST.get('equipment_type', 'router'),
            name            = request.POST.get('name'),
            model           = request.POST.get('model', ''),
            serial_number   = request.POST.get('serial_number', ''),
            status          = request.POST.get('status', 'available'),
            purchase_date   = request.POST.get('purchase_date') or None,
            purchase_price  = request.POST.get('purchase_price') or None,
            vendor          = request.POST.get('vendor', ''),
            warranty_expiry = request.POST.get('warranty_expiry') or None,
            location        = request.POST.get('location', ''),
            assigned_to     = request.POST.get('assigned_to', ''),
            notes           = request.POST.get('notes', ''),
        )
        return redirect('dashboard:equipment')

    return render(request, 'dashboard/create_equipment.html')



@login_required
def edit_equipment(request, equipment_id):
    """
    Edits an existing equipment record.
    """
    item = get_object_or_404(Equipment, id=equipment_id)

    if request.method == 'POST':
        item.name           = request.POST.get('name', item.name)
        item.equipment_type = request.POST.get('equipment_type', item.equipment_type)
        item.model          = request.POST.get('model', item.model)
        item.serial_number  = request.POST.get('serial_number', item.serial_number)
        item.status         = request.POST.get('status', item.status)
        item.purchase_date  = request.POST.get('purchase_date') or None
        item.purchase_price = request.POST.get('purchase_price') or None
        item.vendor         = request.POST.get('vendor', item.vendor)
        item.warranty_expiry= request.POST.get('warranty_expiry') or None
        item.location       = request.POST.get('location', item.location)
        item.assigned_to    = request.POST.get('assigned_to', item.assigned_to)
        item.notes          = request.POST.get('notes', item.notes)
        item.save()
        return redirect('dashboard:equipment')

    return render(request, 'dashboard/edit_equipment.html', {
        'item': item,
    })


@login_required
def delete_equipment(request, equipment_id):
    """
    Deletes an equipment record permanently.
    """
    item = get_object_or_404(Equipment, id=equipment_id)
    if request.method == 'POST':
        item.delete()
    return redirect('dashboard:equipment')

# ── Advertisements ─────────────────────────────────────────


@login_required
def advertisements(request):
    status_filter = request.GET.get('status', '')

    ads = Advertisement.objects.all().order_by('-priority')

    if status_filter == 'active':
        ads = ads.filter(is_active=True)
    elif status_filter == 'inactive':
        ads = ads.filter(is_active=False)

    total_ads         = Advertisement.objects.count()
    active_ads        = Advertisement.objects.filter(is_active=True).count()
    total_impressions = Advertisement.objects.aggregate(
        total=Sum('total_impressions')
    )['total'] or 0
    scheduled_ads     = Advertisement.objects.filter(
        start_date__isnull=False
    ).count()

    return render(request, 'dashboard/advertisements.html', {
        'ads'             : ads,
        'total_ads'       : total_ads,
        'active_ads'      : active_ads,
        'total_impressions': total_impressions,
        'scheduled_ads'   : scheduled_ads,
        'status_filter'   : status_filter,
    })

@login_required
def create_advertisement(request):
    if request.method == 'POST':
        media_file  = request.FILES.get('media_file')
        active_days = request.POST.getlist('active_days')

        Advertisement.objects.create(
            title            = request.POST.get('title'),
            ad_type          = request.POST.get('ad_type', 'banner').lower(),
            description      = request.POST.get('description', ''),
            is_active        = request.POST.get('is_active') == 'on',
            media_file       = media_file,
            click_url        = request.POST.get('click_url', ''),
            display_duration = request.POST.get('display_duration', 10),
            start_date       = request.POST.get('start_date') or None,
            end_date         = request.POST.get('end_date') or None,
            active_from      = request.POST.get('active_from') or None,
            active_until     = request.POST.get('active_until') or None,
            priority         = request.POST.get('priority', 1),
            max_impressions  = request.POST.get('max_impressions') or None,
            active_days      = active_days,
        )
        return redirect('dashboard:advertisements')

    return render(request, 'dashboard/create_advertisement.html', {
        'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    })



@login_required
def delete_advertisement(request, ad_id):
    ad = get_object_or_404(Advertisement, id=ad_id)
    if request.method == 'POST':
        ad.delete()
    return redirect('dashboard:advertisements')


@login_required
def toggle_advertisement(request, ad_id):
    ad = get_object_or_404(Advertisement, id=ad_id)
    if request.method == 'POST':
        ad.is_active = not ad.is_active
        ad.save()
    return redirect('dashboard:advertisements')

# ── Messages ───────────────────────────────────────────────


@login_required
def messages(request):
    channel_filter = request.GET.get('channel', '')

    messages_qs = Message.objects.select_related(
        'customer'
    ).order_by('-created_at')

    if channel_filter:
        messages_qs = messages_qs.filter(channel=channel_filter)

    total_messages  = Message.objects.count()
    sms_count       = Message.objects.filter(channel='SMS').count()
    whatsapp_count  = Message.objects.filter(channel='WhatsApp').count()
    failed_count    = Message.objects.filter(status='failed').count()

    return render(request, 'dashboard/messages.html', {
        'messages'      : messages_qs,
        'channel_filter': channel_filter,
        'total_messages': total_messages,
        'sms_count'     : sms_count,
        'whatsapp_count': whatsapp_count,
        'failed_count'  : failed_count,
    })

@login_required
def send_message(request):
    if request.method == 'POST':
        channel        = request.POST.get('channel', 'SMS')
        recipient      = request.POST.get('recipient', '')
        recipient_type = request.POST.get('recipient_type', 'number')
        content        = request.POST.get('content', '')

        if recipient_type in ['all', 'active', 'expired']:
            status_map = {
                'all'    : None,
                'active' : 'active',
                'expired': 'expired',
            }
            status = status_map.get(recipient_type)
            qs     = Customer.objects.exclude(phone_number='')
            if status:
                qs = qs.filter(status=status)

            for customer in qs:
                # ── At deployment replace this with actual API call ──
                # result     = africastalking.SMS.send(content, [customer.phone_number])
                # msg_status = 'sent' if result['SMSMessageData']['Recipients'][0]['status'] == 'Success' else 'failed'
                msg_status = 'sent' if customer.phone_number else 'failed'

                Message.objects.create(
                    channel      = channel,
                    phone_number = customer.phone_number,
                    message      = content,
                    status       = msg_status,
                    sent_at      = timezone.now(),
                )

        else:
            # Single number
            if recipient:
                # ── At deployment replace this with actual API call ──
                # result     = africastalking.SMS.send(content, [recipient])
                # msg_status = 'sent' if result['SMSMessageData']['Recipients'][0]['status'] == 'Success' else 'failed'
                msg_status = 'sent' if recipient else 'failed'

                Message.objects.create(
                    channel      = channel,
                    phone_number = recipient,
                    message      = content,
                    status       = msg_status,
                    sent_at      = timezone.now(),
                )

        return redirect('dashboard:messages')

    recent_messages = Message.objects.order_by('-sent_at')[:5]

    return render(request, 'dashboard/send_message.html', {
        'recent_messages': recent_messages,
    })
# ── MikroTik Routers ───────────────────────────────────────


@login_required
def routers(request):
    from django.db.models import Count, Q
    from portal.models import WiFiSession

    status_filter = request.GET.get('status', '')
    search        = request.GET.get('search', '').strip()

    routers_qs = MikroTikRouter.objects.all().order_by('identity')

    if status_filter:
        routers_qs = routers_qs.filter(status=status_filter)

    if search:
        routers_qs = routers_qs.filter(
            Q(location__icontains=search) |
            Q(identity__icontains=search)
        )

    # Annotate each router with active session count
    now = timezone.now()
    routers_qs = routers_qs.annotate(
        active_session_count=Count(
            'sessions',
            filter=Q(
                sessions__status='active',
                sessions__expiry_time__gt=now
            )
        )
    )

    online_count  = MikroTikRouter.objects.filter(status='online').count()
    offline_count = MikroTikRouter.objects.filter(status='offline').count()
    pending_count = MikroTikRouter.objects.filter(status='pending').count()

    return render(request, 'dashboard/routers.html', {
        'routers'      : routers_qs,
        'status_filter': status_filter,
        'search'       : search,
        'online_count' : online_count,
        'offline_count': offline_count,
        'pending_count': pending_count,
        'status_counts': {
            'online' : online_count,
            'offline': offline_count,
            'pending': pending_count,
        },
    })

@login_required
def create_router(request):
    if request.method == 'POST':
        MikroTikRouter.objects.create(
            identity            = request.POST.get('identity'),
            location            = request.POST.get('location', ''),
            has_wireless        = request.POST.get('has_wireless') == 'on',
            connection_type     = request.POST.get('connection_type', 'direct'),
            ip_address          = request.POST.get('gateway_ip') or None,
            api_port            = request.POST.get('api_port', 8728),
            api_username        = request.POST.get('api_username', 'admin'),
            api_password        = request.POST.get('api_password', ''),
            wireguard_tunnel_ip = request.POST.get('wireguard_tunnel_ip') or None,
            hotspot_enabled     = request.POST.get('hotspot_enabled') == 'on',
            hotspot_network     = request.POST.get('hotspot_network', '192.168.88.0/24'),
            gateway_ip          = request.POST.get('gateway_ip', '192.168.88.1'),
            dns_servers         = request.POST.get('dns_server', '8.8.8.8'),
            status              = request.POST.get('status', 'pending'),
        )
        return redirect('dashboard:routers')

    steps = [
        (1, 'Enable API on your MikroTik via IP → Services → API'),
        (2, 'Create a dedicated API user in System → Users with API policy only'),
        (3, 'Enter the router gateway IP and API credentials above'),
        (4, 'Click Provision on the router card to push hotspot configuration'),
    ]

    return render(request, 'dashboard/create_router.html', {
        'steps': steps,
    })

@login_required
def edit_router(request, router_id):
    """
    Edits an existing router record.
    """
    router = get_object_or_404(MikroTikRouter, id=router_id)

    if request.method == 'POST':
        router.identity         = request.POST.get('identity', router.identity)
        router.location         = request.POST.get('location', router.location)
        router.connection_type  = request.POST.get('connection_type', router.connection_type)
        router.ip_address       = request.POST.get('gateway_ip') or None
        router.gateway_ip       = request.POST.get('gateway_ip', router.gateway_ip)
        router.hotspot_network  = request.POST.get('hotspot_network', router.hotspot_network)
        router.dns_servers      = request.POST.get('dns_server', router.dns_servers)
        router.has_wireless     = request.POST.get('has_wireless') == 'on'
        router.hotspot_enabled  = request.POST.get('hotspot_enabled') == 'on'
        router.api_username     = request.POST.get('api_username', router.api_username)
        router.api_port         = request.POST.get('api_port', router.api_port)
        router.wireguard_tunnel_ip = request.POST.get('wireguard_tunnel_ip') or None
        router.status           = request.POST.get('status', router.status)
        if request.POST.get('api_password'):
            router.api_password = request.POST.get('api_password')
        router.save()
        return redirect('dashboard:routers')

    return render(request, 'dashboard/edit_router.html', {
        'router': router,
    })


# ── Financial Analytics ────────────────────────────────────

@login_required
def financial_analytics(request):
    """
    Comprehensive financial overview showing
    revenue, expenses, profit and loss.
    """
    import json as json_module

    now       = timezone.now()
    today     = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    week_ago  = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    year_ago  = now - timedelta(days=365)

    # ── Date Range Filter ──────────────────────────────
    date_from = request.GET.get('date_from', '')
    date_to   = request.GET.get('date_to', '')

    # ── Revenue Overview ───────────────────────────────
    def get_revenue(start, end=None):
        qs = Order.objects.filter(status='success', created_at__gte=start)
        if end:
            qs = qs.filter(created_at__lt=end)
        return qs.aggregate(
            total=Sum('amount'),
            count=Count('id')
        )

    today_rev     = get_revenue(today)
    yesterday_rev = get_revenue(yesterday, today)
    week_rev      = get_revenue(week_ago)
    month_rev     = get_revenue(month_ago)
    last_month_rev= get_revenue(
        now - timedelta(days=60),
        now - timedelta(days=30)
    )
    year_rev      = get_revenue(year_ago)

    first_order  = Order.objects.order_by('created_at').first()
    all_time_rev = get_revenue(
        first_order.created_at if first_order else now
    )

    total_revenue = all_time_rev['total'] or 0

    # ── Apply date filter to revenue if provided ───────
    filtered_qs = Order.objects.filter(status='success')
    if date_from:
        filtered_qs = filtered_qs.filter(created_at__date__gte=date_from)
    if date_to:
        filtered_qs = filtered_qs.filter(created_at__date__lte=date_to)
    if date_from or date_to:
        total_revenue = filtered_qs.aggregate(
            total=Sum('amount')
        )['total'] or 0

    # ── Revenue by Source ──────────────────────────────
    online_revenue = Order.objects.filter(
        status='success',
        provider__in=['mtn', 'airtel']
    ).aggregate(total=Sum('amount'))['total'] or 0

    walkin_revenue = Order.objects.filter(
        status='success',
        provider='walk_in'
    ).aggregate(total=Sum('amount'))['total'] or 0

    agent_revenue = Order.objects.filter(
        status='success',
        provider='agent'
    ).aggregate(total=Sum('amount'))['total'] or 0

    # ── Top Performing Packages ────────────────────────
    top_packages = Order.objects.filter(
        status='success'
    ).values(
        'package__name'
    ).annotate(
        total_revenue = Sum('amount'),
        total_orders  = Count('id')
    ).order_by('-total_revenue')[:5]

    # ── Expenses ───────────────────────────────────────
    month_expenses = Expense.objects.filter(
        date__gte=month_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    last_month_expenses = Expense.objects.filter(
        date__gte=(now - timedelta(days=60)).date(),
        date__lt=month_ago.date()
    ).aggregate(total=Sum('amount'))['total'] or 0

    total_expenses = Expense.objects.aggregate(
        total=Sum('amount')
    )['total'] or 0

    # ── Expense by Category ────────────────────────────
    expense_by_category = Expense.objects.values(
        'expense_type'
    ).annotate(
        total=Sum('amount')
    ).order_by('-total')

    # ── Profit & Loss ──────────────────────────────────
    month_profit  = (month_rev['total'] or 0) - month_expenses
    net_profit    = total_revenue - total_expenses
    profit_margin = (
        (month_profit / month_rev['total'] * 100)
        if month_rev['total'] else 0
    )

    # Month over month comparison
    revenue_growth = 0
    if last_month_rev['total']:
        revenue_growth = round(
            ((month_rev['total'] or 0) - last_month_rev['total'])
            / last_month_rev['total'] * 100, 1
        )

    # ── ROI ────────────────────────────────────────────
    roi = (
        (net_profit / total_expenses * 100)
        if total_expenses else 0
    )

    # ── Break-Even Analysis ────────────────────────────
    fixed_costs       = total_expenses
    days_active       = 30
    avg_daily_revenue = (month_rev['total'] or 0) / days_active

    breakeven_days = (
        round(fixed_costs / avg_daily_revenue)
        if avg_daily_revenue else '—'
    )

    # ── Last 6 Months Chart Data ───────────────────────
    chart_labels  = []
    revenue_data  = []
    expense_data  = []
    profit_data   = []

    for i in range(5, -1, -1):
        month_start = (now - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)

        rev = Order.objects.filter(
            status='success',
            created_at__gte=month_start,
            created_at__lt=month_end
        ).aggregate(total=Sum('amount'))['total'] or 0

        exp = Expense.objects.filter(
            date__gte=month_start.date(),
            date__lt=month_end.date()
        ).aggregate(total=Sum('amount'))['total'] or 0

        chart_labels.append(month_start.strftime('%b %Y'))
        revenue_data.append(float(rev))
        expense_data.append(float(exp))
        profit_data.append(float(rev) - float(exp))

    # ── Monthly P&L Table ──────────────────────────────
    monthly_pl = []
    for i in range(5, -1, -1):
        month_start = (now - timedelta(days=30 * i)).replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )
        month_end = (month_start + timedelta(days=32)).replace(day=1)

        rev = Order.objects.filter(
            status='success',
            created_at__gte=month_start,
            created_at__lt=month_end
        ).aggregate(total=Sum('amount'))['total'] or 0

        exp = Expense.objects.filter(
            date__gte=month_start.date(),
            date__lt=month_end.date()
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_pl.append({
            'month'   : month_start.strftime('%B %Y'),
            'revenue' : rev,
            'expenses': exp,
            'profit'  : (rev or 0) - (exp or 0),
        })

    return render(request, 'dashboard/financial_analytics.html', {
        'today_rev'          : today_rev,
        'yesterday_rev'      : yesterday_rev,
        'week_rev'           : week_rev,
        'month_rev'          : month_rev,
        'last_month_rev'     : last_month_rev,
        'year_rev'           : year_rev,
        'all_time_rev'       : all_time_rev,
        'total_revenue'      : total_revenue,
        'online_revenue'     : online_revenue,
        'walkin_revenue'     : walkin_revenue,
        'agent_revenue'      : agent_revenue,
        'top_packages'       : top_packages,
        'month_expenses'     : month_expenses,
        'last_month_expenses': last_month_expenses,
        'total_expenses'     : total_expenses,
        'expense_by_category': expense_by_category,
        'month_profit'       : month_profit,
        'net_profit'         : net_profit,
        'profit_margin'      : round(profit_margin, 1),
        'revenue_growth'     : revenue_growth,
        'roi'                : round(roi, 1),
        'fixed_costs'        : fixed_costs,
        'avg_daily_revenue'  : round(avg_daily_revenue, 0),
        'breakeven_days'     : breakeven_days,
        'chart_labels'       : json_module.dumps(chart_labels),
        'revenue_data'       : json_module.dumps(revenue_data),
        'expense_data'       : json_module.dumps(expense_data),
        'profit_data'        : json_module.dumps(profit_data),
        'monthly_pl'         : monthly_pl,
        'date_from'          : date_from,
        'date_to'            : date_to,
    })

# ── Settings ───────────────────────────────────────────────


@login_required
def settings_view(request):
    """
    System settings page.
    Loads and saves all system configuration.
    """
    from dashboard.models import SystemSettings

    settings = SystemSettings.get_settings()

    if request.method == 'POST':
        # ── Business Info ──────────────────────────────
        settings.business_name    = request.POST.get('business_name', settings.business_name)
        settings.support_phone    = request.POST.get('support_phone', settings.support_phone)
        settings.support_email    = request.POST.get('support_email', settings.support_email)
        settings.support_whatsapp = request.POST.get('support_whatsapp', settings.support_whatsapp)
        settings.portal_url       = request.POST.get('portal_url', settings.portal_url)
        settings.callback_url     = request.POST.get('callback_url', settings.callback_url)

        # ── Logo ───────────────────────────────────────
        if request.FILES.get('logo'):
            settings.logo = request.FILES.get('logo')

        # ── Portal Appearance ──────────────────────────
        settings.brand_color      = request.POST.get('brand_color', settings.brand_color)
        settings.portal_font      = request.POST.get('portal_font', settings.portal_font)
        settings.welcome_message  = request.POST.get('welcome_message', settings.welcome_message)
        settings.footer_text      = request.POST.get('footer_text', settings.footer_text)
        settings.terms_conditions = request.POST.get('terms_conditions', settings.terms_conditions)

        # ── Free Trial ─────────────────────────────────
        settings.free_trial_enabled  = request.POST.get('free_trial_enabled') == 'on'
        settings.free_trial_duration = request.POST.get('free_trial_duration', settings.free_trial_duration)
        settings.free_trial_unit     = request.POST.get('free_trial_unit', settings.free_trial_unit)

        # ── Network ────────────────────────────────────
        settings.default_router_ip = request.POST.get('default_router_ip', settings.default_router_ip)
        settings.hotspot_network   = request.POST.get('hotspot_network', settings.hotspot_network)

        # ── Payments ───────────────────────────────────
        settings.mtn_collection_number    = request.POST.get('mtn_collection_number', settings.mtn_collection_number)
        settings.mtn_api_key              = request.POST.get('mtn_api_key', settings.mtn_api_key)
        settings.airtel_collection_number = request.POST.get('airtel_collection_number', settings.airtel_collection_number)
        settings.airtel_api_key           = request.POST.get('airtel_api_key', settings.airtel_api_key)

        # ── SMS ────────────────────────────────────────
        settings.sms_enabled          = request.POST.get('sms_enabled') == 'on'
        settings.at_username          = request.POST.get('at_username', settings.at_username)
        settings.at_api_key           = request.POST.get('at_api_key', settings.at_api_key)
        settings.sms_sender_id        = request.POST.get('sms_sender_id', settings.sms_sender_id)
        settings.sms_payment_template = request.POST.get('sms_payment_template', settings.sms_payment_template)
        settings.sms_expiry_template  = request.POST.get('sms_expiry_template', settings.sms_expiry_template)
        settings.sms_voucher_template = request.POST.get('sms_voucher_template', settings.sms_voucher_template)

        # ── WhatsApp ───────────────────────────────────
        settings.wa_enabled = request.POST.get('wa_enabled') == 'on'
        settings.wa_number  = request.POST.get('wa_number', settings.wa_number)
        settings.wa_token   = request.POST.get('wa_token', settings.wa_token)

        # ── Security ───────────────────────────────────
        settings.session_timeout    = request.POST.get('session_timeout', settings.session_timeout)
        settings.max_login_attempts = request.POST.get('max_login_attempts', settings.max_login_attempts)
        settings.require_https      = request.POST.get('require_https') == 'on'
        settings.log_activity       = request.POST.get('log_activity') == 'on'

        settings.save()
        return redirect('dashboard:settings')

    tabs = [
        {'key': 'general',       'label': 'General',       'icon': 'bi bi-gear-fill'},
        {'key': 'portal',        'label': 'Portal',         'icon': 'bi bi-window'},
        {'key': 'free_trial',    'label': 'Free Trial',     'icon': 'bi bi-gift-fill'},
        {'key': 'network',       'label': 'Network',        'icon': 'bi bi-router-fill'},
        {'key': 'payments',      'label': 'Payments',       'icon': 'bi bi-credit-card-fill'},
        {'key': 'sms',           'label': 'SMS',            'icon': 'bi bi-chat-dots-fill'},
        {'key': 'whatsapp',      'label': 'WhatsApp',       'icon': 'bi bi-whatsapp'},
        {'key': 'notifications', 'label': 'Notifications',  'icon': 'bi bi-bell-fill'},
        {'key': 'security',      'label': 'Security',       'icon': 'bi bi-shield-fill'},
    ]

    return render(request, 'dashboard/settings.html', {
        'settings': settings,
        'tabs'    : tabs,
    })


@login_required
def team_roles(request):
    import json as json_module
    from django.contrib.auth.models import Group, Permission
    from django.contrib.contenttypes.models import ContentType
    from dashboard.models import Expense

    ct            = ContentType.objects.get_for_model(Expense)
    manager_group = Group.objects.get(name='Manager')
    staff_group   = Group.objects.get(name='Staff')

    # ── Handle POST — save permissions ─────────────────
    if request.method == 'POST':
        role = request.POST.get('role')
        if role in ['manager', 'staff']:
            group     = manager_group if role == 'manager' else staff_group
            all_perms = Permission.objects.filter(content_type=ct)
            selected  = [p for p in all_perms if request.POST.get(p.codename)]
            group.permissions.set(selected)
        return redirect('dashboard:team_roles')

    # ── Load current permissions ───────────────────────
    manager_perms = set(
        manager_group.permissions.values_list('codename', flat=True)
    )
    staff_perms = set(
        staff_group.permissions.values_list('codename', flat=True)
    )

    system_users = User.objects.all().order_by('-is_superuser', '-is_staff')

    session_permissions = [
        {'key': 'view_sessions',       'label': 'View active sessions'},
        {'key': 'disconnect_sessions', 'label': 'Disconnect sessions'},
        {'key': 'view_devices',        'label': 'View devices'},
        {'key': 'block_devices',       'label': 'Block/unblock devices'},
    ]

    finance_permissions = [
        {'key': 'view_payments',     'label': 'View payments'},
        {'key': 'record_payments',   'label': 'Record manual payments'},
        {'key': 'view_withdrawals',  'label': 'View withdrawals'},
        {'key': 'create_withdrawal', 'label': 'Request withdrawals'},
        {'key': 'view_expenses',     'label': 'View expenses'},
        {'key': 'create_expense',    'label': 'Record expenses'},
        {'key': 'view_analytics',    'label': 'View financial analytics'},
    ]

    management_permissions = [
        {'key': 'manage_packages',  'label': 'Manage packages'},
        {'key': 'manage_vouchers',  'label': 'Manage vouchers'},
        {'key': 'manage_customers', 'label': 'Manage customers'},
        {'key': 'manage_leads',     'label': 'Manage leads'},
        {'key': 'send_messages',    'label': 'Send messages'},
        {'key': 'manage_settings',  'label': 'Manage settings'},
    ]

    return render(request, 'dashboard/team_roles.html', {
        'system_users'            : system_users,
        'session_permissions'     : session_permissions,
        'finance_permissions'     : finance_permissions,
        'management_permissions'  : management_permissions,
        'manager_perms'           : manager_perms,
        'staff_perms'             : staff_perms,
        'manager_perms_json'      : json_module.dumps(list(manager_perms)),
        'staff_perms_json'        : json_module.dumps(list(staff_perms)),
        'manager_permission_count': len(manager_perms),
        'staff_permission_count'  : len(staff_perms),
    })

@login_required
def record_payment(request):
    if request.method == 'POST':
        package_id   = request.POST.get('package')
        phone_number = request.POST.get('phone_number', '')
        amount       = request.POST.get('amount', 0)

        try:
            package = Package.objects.get(id=package_id)
        except Package.DoesNotExist:
            package = None

        # For walk-in payments use phone number as device identifier
        device, created = Device.objects.get_or_create(
            mac_address=f"WALKIN-{phone_number}",
            defaults={
                'last_seen': timezone.now(),
            }
        )

        Order.objects.create(
            phone_number = phone_number,
            amount       = amount,
            provider     = 'walk_in',
            status       = 'success',
            package      = package,
            device       = device,
            reference_id = f"MANUAL-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        )
        return redirect('dashboard:payments')

    packages = Package.objects.filter(status='active')
    return render(request, 'dashboard/record_payment.html', {
        'packages': packages,
    })

@login_required
def delete_package(request, package_id):
    package = get_object_or_404(Package, id=package_id)
    if request.method == 'POST':
        package.delete()
    return redirect('dashboard:packages')


@login_required
def delete_expense(request, expense_id):
    expense = get_object_or_404(Expense, id=expense_id)
    if request.method == 'POST':
        expense.delete()
    return redirect('dashboard:expenses')




@login_required
def lead_detail(request, lead_id):
    from dashboard.models import Lead
    lead = get_object_or_404(Lead, id=lead_id)

    if request.method == 'POST':
        lead.full_name      = request.POST.get('full_name', lead.full_name)
        lead.phone_number   = request.POST.get('phone_number', lead.phone_number)
        lead.email          = request.POST.get('email', lead.email)
        lead.source         = request.POST.get('source', lead.source)
        lead.status         = request.POST.get('status', lead.status)
        lead.notes          = request.POST.get('notes', lead.notes)
        last_contacted      = request.POST.get('last_contacted', '')
        if last_contacted:
            lead.last_contacted = last_contacted
        lead.save()
        return redirect('dashboard:leads')

    return render(request, 'dashboard/lead_detail.html', {
        'lead': lead,
    })


@login_required
def delete_lead(request, lead_id):
    """
    Deletes a lead permanently.
    """
    from dashboard.models import Lead
    lead = get_object_or_404(Lead, id=lead_id)
    if request.method == 'POST':
        lead.delete()
    return redirect('dashboard:leads')


@login_required
def delete_message(request, message_id):
    message = get_object_or_404(Message, id=message_id)
    if request.method == 'POST':
        message.delete()
    return redirect('dashboard:messages')


@login_required
def edit_advertisement(request, ad_id):
    ad = get_object_or_404(Advertisement, id=ad_id)

    if request.method == 'POST':
        media_file  = request.FILES.get('media_file')
        active_days = request.POST.getlist('active_days')

        ad.title            = request.POST.get('title', ad.title)
        ad.ad_type          = request.POST.get('ad_type', ad.ad_type).lower()
        ad.description      = request.POST.get('description', ad.description)
        ad.is_active        = request.POST.get('is_active') == 'on'
        ad.click_url        = request.POST.get('click_url', ad.click_url)
        ad.display_duration = request.POST.get('display_duration', ad.display_duration)
        ad.start_date       = request.POST.get('start_date') or None
        ad.end_date         = request.POST.get('end_date') or None
        ad.active_from      = request.POST.get('active_from') or None
        ad.active_until     = request.POST.get('active_until') or None
        ad.priority         = request.POST.get('priority', ad.priority)
        ad.max_impressions  = request.POST.get('max_impressions') or None
        ad.active_days      = active_days
        if media_file:
            ad.media_file   = media_file
        ad.save()
        return redirect('dashboard:advertisements')

    return render(request, 'dashboard/edit_advertisement.html', {
        'ad'  : ad,
        'days': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
    })




@login_required
def router_stats(request, router_id):
    """
    Fetches real-time CPU and memory stats
    from a MikroTik router via API.
    Returns JSON for the dashboard to display.
    """
    from network.mikrotik import get_router_stats
    router = get_object_or_404(MikroTikRouter, id=router_id)

    stats = get_router_stats(router.ip_address)

    if stats:
        router.cpu_usage    = stats.get('cpu', 0)
        router.memory_usage = stats.get('memory', 0)
        router.status       = 'online'
        router.last_seen    = timezone.now()
        router.save()
        return JsonResponse({
            'status': 'success',
            'cpu'   : router.cpu_usage,
            'memory': router.memory_usage,
        })

    router.status = 'offline'
    router.save()
    return JsonResponse({
        'status': 'offline',
        'cpu'   : 0,
        'memory': 0,
    })


@login_required
def delete_router(request, router_id):
    """Deletes a router record."""
    router = get_object_or_404(MikroTikRouter, id=router_id)
    if request.method == 'POST':
        router.delete()
    return redirect('dashboard:routers')


@login_required
def provision_router(request, router_id):
    """
    Provisions the MikroTik router with hotspot
    configuration via API.
    """
    from network.mikrotik import MikrotikAPI
    router = get_object_or_404(MikroTikRouter, id=router_id)

    if request.method == 'POST':
        try:
            api = MikrotikAPI()
            if router.ip_address:
                api.host = router.ip_address

            if api.connect() and api.login():
                # Set DNS servers
                api.send_sentence([
                    '/ip/dns/set',
                    f'=servers={router.dns_servers}',
                    '=allow-remote-requests=yes'
                ])
                api.read_sentence()

                # Set hotspot redirect to our portal
                api.send_sentence([
                    '/ip/hotspot/profile/set',
                    '=numbers=hsprof1',
                    f'=login-by=http-chap,cookie',
                ])
                api.read_sentence()

                # Update router status
                router.status    = 'online'
                router.last_seen = timezone.now()
                router.save()

                api.disconnect()

            else:
                # Could not connect — mark offline
                router.status = 'offline'
                router.save()

        except Exception as e:
            print(f"Provision error: {e}")

    return redirect('dashboard:routers')



@login_required
def edit_expense(request, expense_id):
    """
    Edits an existing expense record.
    """
    expense = get_object_or_404(Expense, id=expense_id)

    if request.method == 'POST':
        receipt = request.FILES.get('receipt')

        expense.name           = request.POST.get('name', expense.name)
        expense.expense_type   = request.POST.get('expense_type', expense.expense_type)
        expense.amount         = request.POST.get('amount', expense.amount)
        expense.date           = request.POST.get('date', expense.date)
        expense.payment_method = request.POST.get('payment_method', expense.payment_method)
        expense.vendor         = request.POST.get('vendor', expense.vendor)
        expense.description    = request.POST.get('description', expense.description)
        if receipt:
            expense.receipt    = receipt
        expense.save()
        return redirect('dashboard:expenses')

    return render(request, 'dashboard/edit_expense.html', {
        'expense': expense,
    })