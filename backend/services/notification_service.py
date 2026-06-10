"""
TruthShield — Notification Dispatcher Service
"""
import logging
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class NotificationService:
    """Service to coordinate Twilio WhatsApp alerts and slack/webhook dispatches."""

    @staticmethod
    def send_whatsapp_alert(to_number: str, message: str) -> bool:
        """Send a WhatsApp warning alert using Twilio API."""
        if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
            logger.info(f"[Mock Notification] WhatsApp to {to_number}: {message}")
            return True

        try:
            from twilio.rest import Client
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=message,
                from_=settings.TWILIO_WHATSAPP_NUMBER,
                to=f"whatsapp:{to_number}"
            )
            logger.info(f"WhatsApp notification sent to {to_number}")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch Twilio WhatsApp notification: {e}")
            return False

    @staticmethod
    def dispatch_webhook_alert(webhook_url: str, payload: dict) -> bool:
        """Dispatch a JSON webhook alert for enterprise SIEM integration."""
        try:
            import requests
            resp = requests.post(webhook_url, json=payload, timeout=5)
            return resp.status_code < 300
        except Exception as e:
            logger.error(f"Webhook dispatch failed: {e}")
            return False
