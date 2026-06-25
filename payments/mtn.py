import requests
import base64
import uuid
from django.conf import settings


def get_access_token():
    """
    Authenticates with MTN MoMo API and returns an access token.
    This token is required for every API call we make to MTN.
    """

    try:
        # Combine API User and API Key then encode to Base64
        credentials = f"{settings.MTN_API_USER}:{settings.MTN_API_KEY}"
        encoded     = base64.b64encode(credentials.encode()).decode()

        # Request token from MTN
        response = requests.post(
            f"{settings.MTN_BASE_URL}/collection/token/",
            headers={
                "Authorization"            : f"Basic {encoded}",
                "Ocp-Apim-Subscription-Key": settings.MTN_SUBSCRIPTION_KEY,
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
    Sends a payment request to MTN MoMo.
    This triggers the USSD PIN prompt on the customer's phone.
    Returns a dict with status and reference_id.
    """

    # Step 1 — Get access token
    token = get_access_token()
    if not token:
        return {
            'status' : 'error',
            'message': 'Payment service is currently unavailable. Please try again shortly.'
        }

    # Step 2 — Generate a unique reference ID for this transaction
    reference_id = str(uuid.uuid4())

    # Step 3 — Format phone number to international format
    # 0771234567 → 256771234567
    if phone_number.startswith('0'):
        phone_number = '256' + phone_number[1:]

    # Step 4 — Build the payment request payload
    payload = {
        "amount"      : str(amount),
        "currency"    : "EUR",
        "externalId"  : str(order_id),
        "payer"       : {
            "partyIdType": "MSISDN",
            "partyId"    : phone_number
        },
        "payerMessage": "WiFi Payment",
        "payeeNote"   : "WiFi Access Payment"
    }

    try:
        # Step 5 — Send the request to MTN
        response = requests.post(
            f"{settings.MTN_BASE_URL}/collection/v1_0/requesttopay",
            json=payload,
            headers={
                "Authorization"            : f"Bearer {token}",
                "X-Reference-Id"           : reference_id,
                "X-Target-Environment"     : settings.MTN_TARGET_ENV,
                "Ocp-Apim-Subscription-Key": settings.MTN_SUBSCRIPTION_KEY,
                "Content-Type"             : "application/json",
                "X-Callback-Url"           : settings.MTN_CALLBACK_URL,
            },
            timeout=15
        )

        # Step 6 — Return result
        # 202 means MTN accepted the request — NOT yet paid
        if response.status_code == 202:
            return {
                'status'      : 'pending',
                'reference_id': reference_id
            }

        return {
            'status' : 'error',
            'message': f"MTN API error: {response.text}"
        }

    except requests.exceptions.ConnectionError:
        return {
            'status' : 'error',
            'message': 'Cannot reach MTN servers. Check your internet connection.'
        }
    except requests.exceptions.Timeout:
        return {
            'status' : 'error',
            'message': 'MTN server took too long to respond. Please try again.'
        }
    except Exception as e:
        return {
            'status' : 'error',
            'message': 'An unexpected error occurred. Please try again.'
        }


def check_payment_status(reference_id):
    """
    Checks the status of a payment request with MTN.
    Called every 3 seconds by our polling endpoint.
    Returns: 'pending', 'success', or 'failed'
    """

    try:
        token = get_access_token()
        if not token:
            return 'pending'

        response = requests.get(
            f"{settings.MTN_BASE_URL}/collection/v1_0/requesttopay/{reference_id}",
            headers={
                "Authorization"            : f"Bearer {token}",
                "X-Target-Environment"     : settings.MTN_TARGET_ENV,
                "Ocp-Apim-Subscription-Key": settings.MTN_SUBSCRIPTION_KEY,
            },
            timeout=10
        )

        if response.status_code == 200:
            data   = response.json()
            status = data.get('status', '').upper()

            if status == 'SUCCESSFUL':
                return 'success'
            elif status == 'FAILED':
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