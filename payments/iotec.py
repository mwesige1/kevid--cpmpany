import requests
from django.conf import settings


def get_access_token():
    """
    Authenticates with IOTEC Pay API using OAuth2
    client credentials flow.
    Returns access token or None on failure.
    Token expires every 300 seconds (5 minutes).
    """
    try:
        response = requests.post(
            settings.IOTEC_AUTH_URL,
            data={
                'client_id'    : settings.IOTEC_CLIENT_ID,
                'client_secret': settings.IOTEC_CLIENT_SECRET,
                'grant_type'   : 'client_credentials',
            },
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            timeout=15
        )

        if response.status_code == 200:
            return response.json().get('access_token')

        print(f"IOTEC Auth error: {response.status_code} — {response.text}")
        return None

    except requests.exceptions.ConnectionError:
        print("IOTEC Auth: Cannot reach authentication server")
        return None
    except requests.exceptions.Timeout:
        print("IOTEC Auth: Authentication server timed out")
        return None
    except Exception as e:
        print(f"IOTEC Auth unexpected error: {e}")
        return None


def request_payment(phone_number, amount, order_id, provider='mtn'):
    """
    Initiates a mobile money collection request via IOTEC Pay.
    Handles both MTN and Airtel through a single API.

    Args:
        phone_number: Customer's mobile number (e.g. 0771234567)
        amount:       Amount in UGX
        order_id:     Our internal order ID for reconciliation
        provider:     'mtn' or 'airtel' (informational only — IOTEC handles both)

    Returns:
        dict with 'status' and 'reference_id' or 'message'
    """

    # Step 1 — Get access token
    token = get_access_token()
    if not token:
        return {
            'status' : 'error',
            'message': 'Payment service is currently unavailable. Please try again shortly.'
        }

    # Step 2 — Format phone number to Uganda format
    # IOTEC accepts 0XXXXXXXXX or 256XXXXXXXXX
    if phone_number.startswith('+256'):
        phone_number = '0' + phone_number[4:]
    elif phone_number.startswith('256'):
        phone_number = '0' + phone_number[3:]

    # Step 3 — Build collection request payload
    payload = {
    'category'   : 'MobileMoney',
    'currency'   : 'UGX',
    'walletId'   : settings.IOTEC_WALLET_ID,
    'externalId' : str(order_id),
    'payer'      : phone_number,
    'amount'     : float(amount),
    'payerNote'  : 'WiFi Access Payment',
    'payeeNote'  : f'Order #{order_id}',
    'callbackUrl': settings.IOTEC_CALLBACK_URL,
    }

    try:
        # Step 4 — Send collection request to IOTEC
        response = requests.post(
            f"{settings.IOTEC_BASE_URL}/api/collections/collect",
            json=payload,
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type' : 'application/json',
            },
            timeout=30
        )

        if response.status_code == 200:
            data         = response.json()
            reference_id = data.get('id')  # IOTEC transaction UUID
            status       = data.get('status', '').lower()

            if reference_id:
                print(f"✅ IOTEC payment initiated: {reference_id} — status: {status}")
                return {
                    'status'      : 'pending',
                    'reference_id': reference_id,
                }

        print(f"IOTEC collection error: {response.status_code} — {response.text}")
        return {
            'status' : 'error',
            'message': f'Payment initiation failed. Please try again.'
        }

    except requests.exceptions.ConnectionError:
        return {
            'status' : 'error',
            'message': 'Cannot reach payment servers. Check your internet connection.'
        }
    except requests.exceptions.Timeout:
        return {
            'status' : 'error',
            'message': 'Payment server took too long to respond. Please try again.'
        }
    except Exception as e:
        print(f"IOTEC payment unexpected error: {e}")
        return {
            'status' : 'error',
            'message': 'An unexpected error occurred. Please try again.'
        }


def check_payment_status(reference_id):
    """
    Checks the status of an IOTEC payment by transaction ID.
    Called every 3 seconds by our polling endpoint.

    Args:
        reference_id: The IOTEC transaction UUID returned on initiation

    Returns:
        'pending', 'success', or 'failed'
    """

    try:
        token = get_access_token()
        if not token:
            return 'pending'

        response = requests.get(
            f"{settings.IOTEC_BASE_URL}/api/collections/status/{reference_id}",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type' : 'application/json',
            },
            timeout=15
        )

        if response.status_code == 200:
            data   = response.json()
            status = data.get('status', '').lower()

            print(f"IOTEC status check: {reference_id} → {status}")

            if status == 'success':
                return 'success'
            elif status in ['failed', 'cancelled', 'rejected']:
                return 'failed'
            else:
                # pending, sentovendor, awaitingapproval
                return 'pending'

        print(f"IOTEC status check error: {response.status_code}")
        return 'pending'

    except requests.exceptions.ConnectionError:
        return 'pending'
    except requests.exceptions.Timeout:
        return 'pending'
    except Exception as e:
        print(f"IOTEC status check unexpected error: {e}")
        return 'pending'


def check_payment_status_by_external_id(order_id):
    """
    Checks payment status using our own order ID (externalId).
    Alternative to check_payment_status when we only have order ID.

    Args:
        order_id: Our internal order ID

    Returns:
        'pending', 'success', or 'failed'
    """

    try:
        token = get_access_token()
        if not token:
            return 'pending'

        response = requests.get(
            f"{settings.IOTEC_BASE_URL}/api/collections/external-id/{order_id}",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type' : 'application/json',
            },
            timeout=15
        )

        if response.status_code == 200:
            data   = response.json()
            status = data.get('status', '').lower()

            if status == 'success':
                return 'success'
            elif status in ['failed', 'cancelled', 'rejected']:
                return 'failed'
            else:
                return 'pending'

        return 'pending'

    except Exception:
        return 'pending'