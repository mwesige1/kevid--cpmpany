import requests
import uuid
from django.conf import settings


def get_access_token():
    """
    Authenticates with Airtel Money API and returns an access token.
    Airtel uses OAuth2 client credentials flow — different from MTN.
    """

    try:
        payload = {
            "client_id"    : settings.AIRTEL_CLIENT_ID,
            "client_secret": settings.AIRTEL_CLIENT_SECRET,
            "grant_type"   : "client_credentials"
        }

        response = requests.post(
            f"{settings.AIRTEL_BASE_URL}/auth/oauth2/token",
            json=payload,
            headers={
                "Content-Type": "application/json",
                "Accept"      : "application/json"
            },
            timeout=10
        )

        if response.status_code == 200:
            return response.json().get('access_token')

        return None

    except requests.exceptions.ConnectionError:
        return None
    except requests.exceptions.Timeout:
        return None
    except Exception:
        return None


def request_payment(phone_number, amount, order_id):
    """
    Sends a payment request to Airtel Money.
    This triggers the payment prompt on the customer's phone.
    Returns a dict with status and reference_id.
    """

    # Step 1 — Get access token
    token = get_access_token()
    if not token:
        return {
            'status' : 'error',
            'message': 'Payment service is currently unavailable. Please try again shortly.'
        }

    # Step 2 — Generate unique reference ID
    reference_id = str(uuid.uuid4())

    # Step 3 — Format phone number to international format
    # 0751234567 → 256751234567
    if phone_number.startswith('0'):
        phone_number = '256' + phone_number[1:]

    # Step 4 — Build payment request payload
    payload = {
        "reference"  : str(order_id),
        "subscriber" : {
            "country" : "UG",
            "currency": "UGX",
            "msisdn"  : phone_number
        },
        "transaction": {
            "amount"  : str(amount),
            "country" : "UG",
            "currency": "UGX",
            "id"      : reference_id
        }
    }

    try:
        # Step 5 — Send request to Airtel
        response = requests.post(
            f"{settings.AIRTEL_BASE_URL}/merchant/v1/payments/",
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type" : "application/json",
                "Accept"       : "application/json",
                "X-Country"    : "UG",
                "X-Currency"   : "UGX",
            },
            timeout=15
        )

        # Step 6 — Return result
        if response.status_code == 200:
            data = response.json()
            if data.get('status', {}).get('success'):
                return {
                    'status'      : 'pending',
                    'reference_id': reference_id
                }

        return {
            'status' : 'error',
            'message': f"Airtel API error: {response.text}"
        }

    except requests.exceptions.ConnectionError:
        return {
            'status' : 'error',
            'message': 'Cannot reach Airtel servers. Check your internet connection.'
        }
    except requests.exceptions.Timeout:
        return {
            'status' : 'error',
            'message': 'Airtel server took too long to respond. Please try again.'
        }
    except Exception:
        return {
            'status' : 'error',
            'message': 'An unexpected error occurred. Please try again.'
        }


def check_payment_status(reference_id):
    """
    Checks the status of an Airtel Money payment.
    Called every 3 seconds by our polling endpoint.
    Returns: 'pending', 'success', or 'failed'
    """

    try:
        token = get_access_token()
        if not token:
            return 'pending'

        response = requests.get(
            f"{settings.AIRTEL_BASE_URL}/standard/v1/payments/{reference_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type" : "application/json",
                "Accept"       : "application/json",
                "X-Country"    : "UG",
                "X-Currency"   : "UGX",
            },
            timeout=10
        )

        if response.status_code == 200:
            data   = response.json()
            status = data.get('data', {}) \
                         .get('transaction', {}) \
                         .get('status', '').upper()

            if status == 'TS':
                return 'success'
            elif status in ['TF', 'TA']:
                return 'failed'
            else:
                return 'pending'

        return 'pending'

    except requests.exceptions.ConnectionError:
        return 'pending'
    except requests.exceptions.Timeout:
        return 'pending'
    except Exception:
        return 'pending'