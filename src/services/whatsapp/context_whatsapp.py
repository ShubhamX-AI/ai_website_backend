import logging
import re
from dataclasses import dataclass

import httpx

from src.core.config import settings

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^\d{10,15}$")
_MAX_MESSAGE_LEN = 1024


@dataclass(frozen=True)
class WhatsAppSource:
    user_name: str
    content: str


def is_valid_phone_number(phone: str) -> bool:
    """Return True when phone number is syntactically valid for WhatsApp."""
    if not phone:
        return False
    cleaned = re.sub(r"[^\d]", "", phone.strip())
    return bool(_PHONE_RE.match(cleaned))


def _normalize_phone(phone: str) -> str:
    """Normalize phone to format without + or extra digits."""
    return re.sub(r"[^\d]", "", phone.strip())


def _format_content(snapshot: dict, user_name: str | None = None) -> str:
    """Extract and format content from snapshot for WhatsApp message."""
    email_context = snapshot.get("email_context") or {}
    raw_summary = (
        email_context.get("raw_summary") or snapshot.get("summary") or ""
    ).strip()

    if not raw_summary:
        return "No content available to send."

    lines = re.split(r"(?<=[.!?])\s+", raw_summary)
    bullet_points = []
    for line in lines:
        cleaned = line.strip()
        if cleaned and len(cleaned) > 10:
            bullet_points.append(cleaned)
        if len(bullet_points) >= 4:
            break

    if not bullet_points:
        bullet_points = [raw_summary[:_MAX_MESSAGE_LEN]]

    formatted = " | ".join(bullet_points)
    if len(formatted) > _MAX_MESSAGE_LEN:
        formatted = formatted[: _MAX_MESSAGE_LEN - 3] + "..."

    return formatted


async def send_context_whatsapp(
    recipient_phone: str,
    snapshot: dict,
    user_name: str | None = None,
) -> tuple[bool, str]:
    """
    Send contextual summary via WhatsApp using Meta Graph API (async).

    Args:
        recipient_phone: WhatsApp phone number (10-15 digits)
        snapshot: UI snapshot with content to send
        user_name: User's name for personalization

    Returns:
        Tuple of (success: bool, message: str)
    """
    if not is_valid_phone_number(recipient_phone):
        return (
            False,
            "Invalid phone number format. Use 10-15 digits (e.g., 918697421450).",
        )

    phone_id = settings.WHATSAPP_PHONE_NUMBER_ID
    access_token = settings.WHATSAPP_ACCESS_TOKEN

    if not phone_id or not access_token:
        logger.error("WhatsApp credentials not configured")
        return False, "WhatsApp service is not configured on the server."

    normalized_phone = _normalize_phone(recipient_phone)
    content = _format_content(snapshot, user_name)
    display_name = user_name or "User"

    url = f"https://graph.facebook.com/v22.0/{phone_id}/messages"

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    payload = {
        "messaging_product": "whatsapp",
        "to": normalized_phone,
        "type": "template",
        "template": {
            "name": settings.WHATSAPP_TEMPLATE_NAME,
            "language": {"code": "en_US"},
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": display_name},
                        {"type": "text", "text": content},
                    ],
                }
            ],
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response_data = response.json()

        if response.status_code == 200:
            logger.info("WhatsApp message sent to %s", normalized_phone)
            return True, "WhatsApp message sent successfully."

        error_msg = response_data.get("error", {}).get("message", "Unknown error")
        error_code = response_data.get("error", {}).get("code", response.status_code)
        logger.warning("WhatsApp API error: %s - %s", error_code, error_msg)

        if error_code == 131026:
            return False, "Message failed. Template may not be approved or configured."
        if "not authorized" in str(error_msg).lower():
            return False, "WhatsApp phone number not authorized for this template."
        if "invalid" in str(error_msg).lower():
            return False, "Invalid phone number or template."

        return False, f"Failed to send WhatsApp message: {error_msg}"

    except httpx.TimeoutException:
        logger.error("WhatsApp API request timed out")
        return False, "WhatsApp service timed out. Please try again."
    except httpx.RequestError as exc:
        logger.error("WhatsApp request failed: %s", exc)
        return False, f"Network error sending WhatsApp message: {exc}"
    except Exception as exc:
        logger.error("Unexpected error sending WhatsApp: %s", exc)
        return False, f"Unexpected error: {exc}"
