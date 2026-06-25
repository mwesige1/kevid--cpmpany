import json
import uuid
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta

from portal.models import Package, Device, WiFiSession
from payments.models import Order, Voucher
from . import mtn, airtel, iotec



def get_client_ip(request):
    """
    Gets the real client IP address behind Nginx/Docker proxy.
    Cloudflare and Nginx both set X-Forwarded-For header.
    REMOTE_ADDR inside Docker returns the proxy container IP
    not the real client — so we must check headers first.
    """
    # X-Forwarded-For may contain multiple IPs — take the first one
    # Format: "client_ip, proxy1_ip, proxy2_ip"
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    # Fallback to REMOTE_ADDR if no proxy header present
    return request.META.get('REMOTE_ADDR')

@csrf_exempt
def initiate_payment(request):
    """
    Called when customer clicks PAY NOW on the portal.
    Creates an Order record and initiates mobile money payment.
    """

    # ── CORS helper ────────────────────────────────────
    def cors(data, status=200):
        r = JsonResponse(data, status=status)
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Handle OPTIONS preflight ───────────────────────
    if request.method == 'OPTIONS':
        r = JsonResponse({})
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Only allow POST requests ───────────────────────
    if request.method != 'POST':
        return cors({'status': 'error', 'message': 'Method not allowed'}, status=405)

    # ── Parse JSON body ────────────────────────────────
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return cors({'status': 'error', 'message': 'Invalid request data'}, status=400)

    # ── Extract fields from request ────────────────────
    package_id   = data.get('package_id')
    phone_number = data.get('phone_number')
    provider     = data.get('provider')
    mac_address  = data.get('mac_address')
    is_free      = data.get('is_free', False)

    # ── Get the router this customer is connecting from ─
    router_id = data.get('router_id')
    router    = None
    if router_id:
        try:
            from network.models import MikroTikRouter
            router = MikroTikRouter.objects.get(id=int(router_id))
        except (MikroTikRouter.DoesNotExist, ValueError, TypeError):
            pass

    print(f"DEBUG received: package={package_id}, phone={phone_number}, provider={provider}, mac={mac_address}, is_free={is_free}, router_id={router_id}, router={router}")

    # ── Validate required fields ───────────────────────
    if not all([package_id, mac_address]):
        return cors({'status': 'error', 'message': 'Missing required fields.'}, status=400)

    # ── Get the package ────────────────────────────────
    try:
        package = Package.objects.get(id=package_id, status='active')
    except Package.DoesNotExist:
        return cors({'status': 'error', 'message': 'Package not found or no longer available.'}, status=404)

    # ── Get or create device record ────────────────────
    device, created = Device.objects.get_or_create(mac_address=mac_address)
    if phone_number:
        device.phone_number = phone_number
    device.last_seen = timezone.now()
    if router:
        device.last_router = router
    device.save()

    # ── Check for existing active session ──────────────
    active_session = WiFiSession.objects.filter(
        device=device,
        status='active',
        expiry_time__gt=timezone.now()
    ).first()

    if active_session:
        return cors({
            'status' : 'error',
            'message': 'This device already has an active session.'
        })

    # ── Handle Free Trial ──────────────────────────────
    if is_free or package.is_free_trial:

        # Check if device has already used free trial
        if device.has_used_free_trial:
            return cors({
                'status' : 'error',
                'message': 'Free trial has already been used on this device.'
            })

        ip_address = data.get('ip_address') or get_client_ip(request)

        # Create session immediately — no payment needed
        WiFiSession.objects.create(
            device      = device,
            package     = package,
            ip_address  = ip_address,
            router      = router,
            expiry_time = timezone.now() + timedelta(hours=package.duration_in_hours),
            status      = 'active'
        )

        # Mark device as having used free trial permanently
        device.has_used_free_trial = True
        device.save()

        # Grant internet access on Mikrotik router
        try:
            from network.mikrotik import grant_internet_access
            grant_internet_access(
                mac_address = mac_address,
                ip_address  = ip_address,
                router      = router
            )
        except Exception as e:
            print(f"Router access error: {e}")

        return cors({'status': 'success', 'message': 'Free trial activated successfully.'})

    # ── Handle Paid Packages ───────────────────────────
    if provider not in ['mtn', 'airtel']:
        return cors({'status': 'error', 'message': 'Invalid payment provider.'}, status=400)

    # Validate Uganda phone number format
    import re
    clean_phone = phone_number.replace(' ', '').replace('-', '')
    if not re.match(r'^0\d{9}$', clean_phone):
        return cors({
            'status' : 'error',
            'message': 'Invalid phone number. Please enter a valid 10-digit number starting with 0 (e.g. 0771234567).'
        }, status=400)

    reference_id = str(uuid.uuid4())

    # ── Create Order record ────────────────────────────
    order = Order.objects.create(
        device       = device,
        package      = package,
        phone_number = phone_number,
        amount       = package.price,
        provider     = provider,
        status       = 'pending',
        reference_id = reference_id,
        router       = router,
        ip_address   = data.get('ip_address') or request.META.get('REMOTE_ADDR'),
    )

    # ── Initiate mobile money payment ──────────────────
    # ── Initiate mobile money payment via IOTEC ────────
    # IOTEC handles both MTN and Airtel through one API
    result = iotec.request_payment(
        phone_number = phone_number,
        amount       = package.price,
        order_id     = order.id,
        provider     = provider
    )

    if result['status'] == 'pending':
        order.reference_id = result['reference_id']
        order.save()
        return cors({
            'status'  : 'pending',
            'order_id': order.id,
            'message' : 'Payment initiated. Waiting for confirmation.'
        })
    else:
        order.status = 'failed'
        order.save()
        return cors({
            'status' : 'error',
            'message': result.get('message', 'Payment initiation failed.')
        })


def payment_status(request, order_id):
    """
    Called every 3 seconds by portal JavaScript
    to check if a payment has been confirmed.
    Flow:
    1. Find the order by ID
    2. If already resolved return immediately
    3. If still pending check with MTN/Airtel
    4. If confirmed create WiFiSession and grant access
    """

    # ── CORS helper ────────────────────────────────────
    def cors(data, status=200):
        r = JsonResponse(data, status=status)
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Handle OPTIONS preflight ───────────────────────
    if request.method == 'OPTIONS':
        r = JsonResponse({})
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Step 1 — Find the order ────────────────────────
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return cors({'status': 'error', 'message': 'Order not found.'}, status=404)

    # ── Step 2 — Return immediately if already resolved ─
    # Avoids calling MTN/Airtel API multiple times
    if order.status == 'success':
        return cors({'status': 'success'})

    if order.status == 'failed':
        return cors({'status': 'failed'})

    # ── Step 3 — Check with IOTEC ─────────────────────
    provider_status = iotec.check_payment_status(order.reference_id)

    # ── Step 4 — Handle provider response ─────────────
    if provider_status == 'success':

        # Mark order as paid
        order.status = 'success'
        order.save()

        # Update device total spending for analytics
        order.device.total_spent += order.amount
        order.device.save()

        # Get customer's real IP address
        # Mikrotik sometimes passes its own IP so we check
        # Use the local hotspot IP saved at payment initiation
        # order.ip_address comes from MikroTik ?ip= param — always the correct local IP
        # get_client_ip would return Cloudflare's public IP — wrong for MikroTik rules
        ip_address = order.ip_address or get_client_ip(request)

        # ── Create WiFi session ────────────────────────
        # Links to order.router so we know which
        # Mikrotik router granted this access
        session = WiFiSession.objects.create(
            device      = order.device,
            package     = order.package,
            ip_address  = ip_address,
            router      = order.router,     # Use router from order ← KEY LINE
            expiry_time = timezone.now() + timedelta(
                hours=order.package.duration_in_hours
            ),
            status      = 'active'
        )

        # Link session back to order for tracking
        order.session = session
        order.save()

        # ── Grant internet access on correct router ────
        # Uses router from order — works for remote routers
        # via WireGuard tunnel
        try:
            from network.mikrotik import grant_internet_access
            grant_internet_access(
                mac_address = order.device.mac_address,
                ip_address  = ip_address,
                router      = order.router  # Use correct router ← KEY LINE
            )
        except Exception as e:
            print(f"Router access error: {e}")

        return cors({'status': 'success'})

    elif provider_status == 'failed':
        # Payment rejected or timed out
        order.status = 'failed'
        order.save()
        return cors({'status': 'failed'})

    else:
        # Still waiting for customer to confirm on phone
        return cors({'status': 'pending'})

@csrf_exempt
def mtn_callback(request):
    """
    Receives payment result callbacks from MTN MoMo.
    MTN calls this URL after customer confirms payment.
    This is a backup to polling — handles missed results.
    Always returns 200 to MTN to prevent retries.
    """

    if request.method != 'POST':
        return JsonResponse({'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'message': 'Invalid data'}, status=400)

    # Extract fields from MTN callback payload
    external_id = data.get('externalId')                    # Our order ID
    status      = data.get('status', '').upper()            # SUCCESSFUL or FAILED
    mtn_txn_id  = data.get('financialTransactionId', '')    # MTN transaction ID

    # Find the matching order using our order ID
    try:
        order = Order.objects.get(id=external_id, provider='mtn')
    except Order.DoesNotExist:
        return JsonResponse({'message': 'Order not found'}, status=200)

    # Skip if already processed — prevents duplicate sessions
    if order.status != 'pending':
        return JsonResponse({'message': 'Already processed'}, status=200)

    if status == 'SUCCESSFUL':

        # ── Voucher Purchase ───────────────────────────
        # Skip session creation — session is created on redemption
        if order.order_type == 'voucher':
            order.status      = 'success'
            order.momo_txn_id = mtn_txn_id
            order.save()
            order.device.total_spent += order.amount
            order.device.save()
            return JsonResponse({'message': 'Callback received'}, status=200)

        # ── Direct Payment ─────────────────────────────
        # Mark order as paid
        order.status      = 'success'
        order.momo_txn_id = mtn_txn_id
        order.save()

        # Update device total spending
        order.device.total_spent += order.amount
        order.device.save()

        # Create WiFi session with router from order
        session = WiFiSession.objects.create(
            device      = order.device,
            package     = order.package,
            ip_address  = order.ip_address or '192.168.88.1',
            router      = order.router,
            expiry_time = timezone.now() + timedelta(
                hours=order.package.duration_in_hours
            ),
            status      = 'active'
        )
        order.session = session
        order.save()

        # Grant internet access on correct router
        try:
            from network.mikrotik import grant_internet_access
            grant_internet_access(
                mac_address = order.device.mac_address,
                ip_address  = order.ip_address or '192.168.88.1',
                router      = order.router
            )
        except Exception as e:
            print(f"Router access error: {e}")

    elif status == 'FAILED':
        order.status = 'failed'
        order.save()

    # Always return 200 to MTN
    return JsonResponse({'message': 'Callback received'}, status=200)
@csrf_exempt
def airtel_callback(request):
    """
    Receives payment result callbacks from Airtel Money.
    Airtel status codes:
    TS = Transaction Successful
    TF = Transaction Failed
    TA = Transaction Ambiguous (treat as failed)
    Always returns 200 to Airtel.
    """

    if request.method != 'POST':
        return JsonResponse({'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'message': 'Invalid data'}, status=400)

    # Airtel nests data inside 'transaction' object
    transaction = data.get('transaction', {})
    reference   = transaction.get('id', '')             # Our reference ID
    status      = transaction.get('status', '').upper() # TS, TF, or TA
    airtel_id   = transaction.get('airtel_money_id', '') # Airtel transaction ID

    # Find order by reference ID
    try:
        order = Order.objects.get(reference_id=reference, provider='airtel')
    except Order.DoesNotExist:
        return JsonResponse({'message': 'Order not found'}, status=200)

    # Skip if already processed
    if order.status != 'pending':
        return JsonResponse({'message': 'Already processed'}, status=200)

    if status == 'TS':

        # ── Voucher Purchase ───────────────────────────
        # Skip session creation — session is created on redemption
        if order.order_type == 'voucher':
            order.status      = 'success'
            order.momo_txn_id = airtel_id
            order.save()
            order.device.total_spent += order.amount
            order.device.save()
            return JsonResponse({'message': 'Callback received'}, status=200)

        # ── Direct Payment ─────────────────────────────
        # Transaction Successful
        order.status      = 'success'
        order.momo_txn_id = airtel_id
        order.save()

        # Update device total spending
        order.device.total_spent += order.amount
        order.device.save()

        # Create WiFi session with router from order
        session = WiFiSession.objects.create(
            device      = order.device,
            package     = order.package,
            ip_address  = order.ip_address or '192.168.88.1',
            router      = order.router,
            expiry_time = timezone.now() + timedelta(
                hours=order.package.duration_in_hours
            ),
            status      = 'active'
        )
        order.session = session
        order.save()

        # Grant internet access on correct router
        try:
            from network.mikrotik import grant_internet_access
            grant_internet_access(
                mac_address = order.device.mac_address,
                ip_address  = order.ip_address or '192.168.88.1',
                router      = order.router
            )
        except Exception as e:
            print(f"Router access error: {e}")

    elif status in ['TF', 'TA']:
        # Transaction Failed or Ambiguous — treat as failed
        order.status = 'failed'
        order.save()

    # Always return 200 to Airtel
    return JsonResponse({'message': 'Callback received'}, status=200)


@csrf_exempt
def iotec_callback(request):
    """
    Receives payment result callbacks from IOTEC Pay.
    IOTEC calls this URL when transaction status changes
    to Success, Failed or SentToVendor.
    Always returns 200 to IOTEC.
    """

    if request.method != 'POST':
        return JsonResponse({'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'message': 'Invalid data'}, status=400)

    print(f"IOTEC Callback received: {data}")

    # Extract fields from IOTEC callback payload
    external_id  = data.get('externalId', '')    # Our order ID
    status       = data.get('status', '').lower() # success, failed, sentovendor
    iotec_txn_id = data.get('id', '')             # IOTEC transaction UUID

    # Find the matching order using our order ID
    try:
        order = Order.objects.get(id=external_id)
    except Order.DoesNotExist:
        return JsonResponse({'message': 'Order not found'}, status=200)

    # Skip if already processed
    if order.status != 'pending':
        return JsonResponse({'message': 'Already processed'}, status=200)

    if status == 'success':

        # ── Voucher Purchase ───────────────────────────
        if order.order_type == 'voucher':
            order.status      = 'success'
            order.momo_txn_id = iotec_txn_id
            order.save()
            order.device.total_spent += order.amount
            order.device.save()
            return JsonResponse({'message': 'Callback received'}, status=200)

        # ── Direct Payment ─────────────────────────────
        order.status      = 'success'
        order.momo_txn_id = iotec_txn_id
        order.save()

        # Update device total spending
        order.device.total_spent += order.amount
        order.device.save()

        # Create WiFi session
        session = WiFiSession.objects.create(
            device      = order.device,
            package     = order.package,
            ip_address  = order.ip_address or '192.168.88.1',
            router      = order.router,
            expiry_time = timezone.now() + timedelta(
                hours=order.package.duration_in_hours
            ),
            status      = 'active'
        )
        order.session = session
        order.save()

        # Grant internet access on correct router
        try:
            from network.mikrotik import grant_internet_access
            grant_internet_access(
                mac_address = order.device.mac_address,
                ip_address  = order.ip_address or '192.168.88.1',
                router      = order.router
            )
        except Exception as e:
            print(f"Router access error: {e}")

    elif status == 'failed':
        order.status = 'failed'
        order.save()

    # Always return 200 to IOTEC
    return JsonResponse({'message': 'Callback received'}, status=200)

@csrf_exempt
def redeem_voucher(request):
    """
    Called when customer enters a voucher code on portal.
    Flow:
    1. Validate voucher exists and is available
    2. Get or create device record
    3. Check for existing active session
    4. Mark voucher as used
    5. Create WiFi session on correct router
    6. Grant internet access on correct router
    """

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid request data'}, status=400)

    # Extract fields from request
    voucher_code = data.get('voucher_code', '').upper().strip()
    mac_address  = data.get('mac_address')
    ip_address   = data.get('ip_address') or request.META.get('REMOTE_ADDR')

    # Validate required fields
    if not all([voucher_code, mac_address]):
        return JsonResponse({'status': 'error', 'message': 'Missing required fields.'}, status=400)

    # Find voucher — must be available or giveaway
    try:
        voucher = Voucher.objects.get(
            code=voucher_code,
            status__in=['available', 'giveaway']
        )
    except Voucher.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'Invalid or already used voucher code.'})

    # Get or create device record
    device, created = Device.objects.get_or_create(mac_address=mac_address)
    device.last_seen = timezone.now()
    device.save()

    # Prevent double session on same device
    active_session = WiFiSession.objects.filter(
        device=device,
        status='active',
        expiry_time__gt=timezone.now()
    ).first()

    if active_session:
        return JsonResponse({'status': 'error', 'message': 'This device already has an active session.'})

    # Mark voucher as used
    voucher.status         = 'used'
    voucher.used_by_device = device
    voucher.used_at        = timezone.now()
    voucher.save()

    # Get the router this customer is connecting from
    router_id = data.get('router_id')
    router    = None
    if router_id:
        try:
            from network.models import MikroTikRouter
            router = MikroTikRouter.objects.get(id=router_id)
        except MikroTikRouter.DoesNotExist:
            pass

    # Create WiFi session linked to correct router
    WiFiSession.objects.create(
        device      = device,
        package     = voucher.package,
        ip_address  = ip_address,
        router      = router,           # Use correct router ← KEY LINE
        expiry_time = timezone.now() + timedelta(hours=voucher.package.duration_in_hours),
        status      = 'active'
    )

    # Grant internet access on correct router
    try:
        from network.mikrotik import grant_internet_access
        grant_internet_access(
            mac_address = mac_address,
            ip_address  = ip_address,
            router      = router        # Use correct router ← KEY LINE
        )
    except Exception as e:
        print(f"Router access error: {e}")

    return JsonResponse({'status': 'success', 'message': 'Voucher redeemed successfully. You are now connected.'})


@csrf_exempt
def buy_voucher(request):
    """
    Called when customer buys a voucher via mobile money.
    Flow:
    1. Customer selects package and enters phone number
    2. MoMo payment is initiated
    3. On success — voucher code is generated
    4. Code printed to terminal (SMS later via Africa's Talking)
    5. Customer uses code in Voucher tab to connect
    """

    # ── CORS helper ────────────────────────────────────
    def cors(data, status=200):
        r = JsonResponse(data, status=status)
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Handle OPTIONS preflight ───────────────────────
    if request.method == 'OPTIONS':
        r = JsonResponse({})
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    if request.method != 'POST':
        return cors({'status': 'error', 'message': 'Method not allowed'}, status=405)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return cors({'status': 'error', 'message': 'Invalid request data'}, status=400)

    package_id   = data.get('package_id')
    phone_number = data.get('phone_number')
    provider     = data.get('provider')

    if not all([package_id, phone_number, provider]):
        return cors({'status': 'error', 'message': 'Missing required fields.'}, status=400)

    try:
        package = Package.objects.get(id=package_id, status='active')
    except Package.DoesNotExist:
        return cors({'status': 'error', 'message': 'Package not found.'}, status=404)

    if provider not in ['mtn', 'airtel']:
        return cors({'status': 'error', 'message': 'Invalid payment provider.'}, status=400)

    reference_id = str(uuid.uuid4())

    # Use phone number as virtual MAC for voucher buyer
    # since they are not physically connected to the hotspot
    device, created = Device.objects.get_or_create(
        mac_address=f"V-{phone_number[-10:]}",
        defaults={'last_seen': timezone.now()}
    )

    # Create order — no router needed for voucher purchases
    # because the voucher buyer may not be on our network
    order = Order.objects.create(
        device       = device,
        package      = package,
        phone_number = phone_number,
        amount       = package.price,
        provider     = provider,
        status       = 'pending',
        reference_id = reference_id,
        order_type   = 'voucher',
    )

    result = iotec.request_payment(
    phone_number = phone_number,
    amount       = package.price,
    order_id     = order.id,
    provider     = provider
    )

    if result['status'] == 'pending':
        order.reference_id = result['reference_id']
        order.save()
        return cors({
            'status'  : 'pending',
            'order_id': order.id,
            'message' : 'Payment initiated. Waiting for confirmation.'
        })
    else:
        order.status = 'failed'
        order.save()
        return cors({'status': 'error', 'message': result.get('message', 'Payment initiation failed.')})


@csrf_exempt
def buy_voucher_status(request, order_id):
    """
    Called every 3 seconds to check if voucher payment succeeded.
    On success generates and returns voucher code.
    Later: replace print with SMS via Africa's Talking.
    """

    # ── CORS helper ────────────────────────────────────
    def cors(data, status=200):
        r = JsonResponse(data, status=status)
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # ── Handle OPTIONS preflight ───────────────────────
    if request.method == 'OPTIONS':
        r = JsonResponse({})
        r['Access-Control-Allow-Origin']  = '*'
        r['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        r['Access-Control-Allow-Headers'] = 'Content-Type, X-CSRFToken'
        return r

    # Find the order
    try:
        order = Order.objects.get(id=order_id)
    except Order.DoesNotExist:
        return cors({'status': 'error', 'message': 'Order not found.'}, status=404)

    if order.status == 'success':
        # Check if voucher was already generated for this order
        existing = Voucher.objects.filter(
            batch_reference=f"ORDER-{order.id}"
        ).first()

        if existing:
            # Return already generated voucher code
            return cors({
                'status'      : 'success',
                'voucher_code': existing.code,
                'message'     : f'Your voucher code is: {existing.code}'
            })

        # Generate a unique voucher code
        import random
        chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'
        code  = ''.join(random.choices(chars, k=8))
        while Voucher.objects.filter(code=code).exists():
            code = ''.join(random.choices(chars, k=8))

        # Save the voucher to database
        Voucher.objects.create(
            code            = code,
            package         = order.package,
            status          = 'available',
            batch_reference = f"ORDER-{order.id}",
            sale_type       = 'online',
            price_sold      = order.amount,
        )

        # Print to terminal — replace with SMS in production
        print(f"\n{'='*50}")
        print(f"🎟️  VOUCHER CODE GENERATED")
        print(f"Phone  : {order.phone_number}")
        print(f"Package: {order.package.name}")
        print(f"Code   : {code}")
        print(f"{'='*50}\n")

        # TODO: Uncomment when Africa's Talking is ready
        # from wifiportal.sms import send_voucher_sms
        # send_voucher_sms(order.phone_number, code, order.package.name)

        return cors({
            'status'      : 'success',
            'voucher_code': code,
            'message'     : f'Your voucher code is: {code}'
        })

    elif order.status == 'failed':
        return cors({'status': 'failed'})

    # Still pending — check with provider
    provider_status = iotec.check_payment_status(order.reference_id)

    if provider_status == 'success':
        order.status = 'success'
        order.save()
        # Recursive call to generate voucher
        return buy_voucher_status(request, order_id)

    elif provider_status == 'failed':
        order.status = 'failed'
        order.save()
        return cors({'status': 'failed'})

    # Still pending — tell JavaScript to keep polling
    return cors({'status': 'pending'})