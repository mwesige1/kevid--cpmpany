import africastalking
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def initialize_at():
    """Initialize Africa's Talking SDK."""
    import os
    os.environ['AT_BASE_URL'] = 'https://api.sandbox.africastalking.com'
    
    africastalking.initialize(
        username=settings.AT_USERNAME,
        api_key=settings.AT_API_KEY
    )
    return africastalking.SMS


def send_sms(phone_number, message):
    """
    Sends an SMS to a phone number via Africa's Talking.
    Phone number should be in international format e.g. +256771234567
    Returns True if sent successfully, False otherwise.
    """
    try:
        # Format phone number
        if phone_number.startswith('0'):
            phone_number = '+256' + phone_number[1:]
        elif not phone_number.startswith('+'):
            phone_number = '+256' + phone_number

        sms = initialize_at()

        kwargs = {
            'message'   : message,
            'recipients': [phone_number],
        }

        # Add sender ID if configured
        if settings.AT_SENDER_ID:
            kwargs['sender_id'] = settings.AT_SENDER_ID

        response = sms.send(**kwargs)
        logger.info(f"SMS sent to {phone_number}: {response}")

        # Check if at least one recipient succeeded
        recipients = response.get('SMSMessageData', {}).get('Recipients', [])
        if recipients and recipients[0].get('status') == 'Success':
            return True

        return False

    except Exception as e:
        logger.error(f"SMS send error to {phone_number}: {str(e)}")
        return False


def send_voucher_sms(phone_number, voucher_code, package_name):
    """
    Sends a voucher code to a customer via SMS.
    """
    message = (
        f"Your WiFi voucher code is: {voucher_code}\n"
        f"Package: {package_name}\n"
        f"Connect at: http://192.168.88.252:8000\n"
        f"Enter code in Voucher tab to connect."
    )
    return send_sms(phone_number, message)