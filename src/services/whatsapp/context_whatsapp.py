import logging
import re
from dataclasses import dataclass

import httpx

from src.core.config import settings
from src.services._ai_formatter import llm_text

logger = logging.getLogger(__name__)

_PHONE_RE = re.compile(r"^\d{10,15}$")
_MAX_MESSAGE_LEN = 1024

_SYSTEM_PROMPT = (
    "You format concise WhatsApp messages from UI snapshot data. "
    "CRITICAL RULE: Output must be a SINGLE LINE with NO newlines or tabs whatsoever. "
    "Format: 'Title: item1 | item2 | item3'. "
    "Extract the ACTUAL data (addresses, names, numbers, etc.) — never summarise generically. "
    "No markdown, no asterisks, no greetings, no sign-offs. "
    "Total output must be under 900 characters."
)


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
    """Normalize phone to digits-only format."""
    return re.sub(r"[^\d]", "", phone.strip())


def _fallback_format(snapshot: dict) -> str:
    """
    Plain-text fallback when LLM is unavailable.
    Pulls structured data directly from the snapshot.

    IMPORTANT: Returns a SINGLE LINE — WhatsApp template params forbid newlines.
    Items are joined with ' | ' separator.
    """
    parts: list[str] = []

    title = snapshot.get("title") or snapshot.get("type") or "Information"
    parts.append(str(title))

    # Try details dict first — this is where card data usually lives
    details = snapshot.get("details") or {}
    if isinstance(details, dict):
        for key, value in details.items():
            if key in ("card_count", "source"):
                continue
            if isinstance(value, list):
                for item in value:
                    line = str(item).strip()
                    if line:
                        parts.append(line[:120])
            elif value:
                parts.append(str(value).strip()[:120])

    # Fall back to summary / raw_summary if details was empty
    if len(parts) <= 1:
        raw = (
            (snapshot.get("email_context") or {}).get("raw_summary")
            or snapshot.get("summary")
            or ""
        ).strip()
        if raw:
            parts.append(raw[:800])

    # Join as single line — WhatsApp template params CANNOT contain newlines
    return " | ".join(parts)


def _sanitize(content: str) -> str:
    """
    Enforce WhatsApp template parameter constraints:
    - NO newlines or tabs allowed (Meta API hard rule)
    - Replace any remaining newlines with ' | '
    - Strip trailing/leading whitespace and collapse excess spaces
    """
    # Replace newlines and tabs with the pipe separator
    single_line = content.replace("\r\n", " | ").replace("\n", " | ").replace("\t", " ")
    # Collapse any run of 5+ spaces (Meta also rejects > 4 consecutive spaces)
    import re as _re
    single_line = _re.sub(r" {5,}", "    ", single_line)
    return single_line.strip()


async def _format_content(snapshot: dict) -> str:
    """
    Build the WhatsApp message body from a UI snapshot.

    Strategy:
    1. Ask the LLM to extract and format the real data (same approach as email).
    2. Fall back to a structured plain-text extraction if the LLM is unavailable.
    3. Sanitize for template safety, then truncate to 1024 chars.
    """
    content = await llm_text(snapshot, _SYSTEM_PROMPT) or _fallback_format(snapshot)
    content = _sanitize(content)

    if len(content) > _MAX_MESSAGE_LEN:
        content = content[: _MAX_MESSAGE_LEN - 3] + "..."

    logger.debug("WhatsApp content (%d chars): %s", len(content), content[:120])
    return content


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
    content = await _format_content(snapshot)
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
        # Log the full response body to diagnose exactly which parameter Meta rejected
        logger.warning(
            "WhatsApp API error: %s - %s | full_response=%s",
            error_code,
            error_msg,
            response_data,
        )

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
